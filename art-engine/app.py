import json
import random

from pathlib import Path
from PIL import Image

from utils.parse_yaml import read_yaml

import utils.rich_metadata as rm
import utils.rarity_rank as rr


def make_dirs() -> None:
    """Creates the directories to store creates images and their corresponding json data.
    If the folders already exist, skips and continues.
    """
    print('Creating build directories')
    build_dirs = ['build', 'build/images', 'build/json']

    for _dir in build_dirs:
        _dir = Path(_dir)
        if not _dir.exists():
            print(f'Creating {_dir} directory')
            _dir.mkdir(exist_ok=True)

    print('Build directories created')


def join_layers(config_file: object) -> tuple:
    final_layers = list()

    for layer in config_file['layers']:
        layer_path = Path.cwd() / 'art-engine' / 'assets' / layer['name']
        layers = sorted([trait for trait in layer_path.iterdir() if trait.is_file() and trait.suffix in ['.png', '.jpg', '.jpeg']])

        print(f"Processing layer: {layer['name']}")
        print(f"Layer path: {layer_path}")
        print(f"Number of layers found: {len(layers)}")
        print(f"Layers: {layers}")
        print(f"Rarities: {layer['rarities']}")

        if not layer.get('required', True):
            layers.append('None')
            if len(layer['rarities']) < len(layers):
                layer['rarities'].append(100 - sum(layer['rarities']))
            print(f"Optional layer: {layer['name']}, added 'None' option")

        if len(layers) != len(layer['rarities']):
            print(f"Warning: Mismatch in number of layers ({len(layers)}) and rarities ({len(layer['rarities'])}) for layer {layer['name']}")
            if len(layers) > len(layer['rarities']):
                layer['rarities'].extend([0] * (len(layers) - len(layer['rarities'])))
            else:
                layer['rarities'] = layer['rarities'][:len(layers)]
            print(f"Adjusted rarities: {layer['rarities']}")

        if sum(layer['rarities']) != 100:
            print(f"Warning: Rarities for layer {layer['name']} do not sum to 100. Normalizing...")
            total = sum(layer['rarities'])
            layer['rarities'] = [int((r / total) * 100) for r in layer['rarities']]
            print(f"Normalized rarities: {layer['rarities']}")

        chosen_image = random.choices(layers, weights=layer['rarities'])
        image_path = layer_path / chosen_image[0] if chosen_image[0] != 'None' else 'None'

        final_layers.append(image_path)

    return tuple(final_layers)



def create_metadata(config_file: object, edition: int, final_layers: tuple) -> None:
    token_prefix = config_file['token_prefix']
    token_description = config_file['description']
    uri_prefix = config_file['uri_prefix']

    metadata_dict = {
        'name': f'{token_prefix} #{edition}',
        'description': token_description,
        'image': f'{uri_prefix}baseURI/{edition}.png',
        'edition': edition,
        'attributes': []
    }

    for layer, config_layer in zip(final_layers, config_file['layers']):
        if layer != 'None':
            attributes_dict = {
                'trait_type': config_layer['name'],
                'value': layer.stem
            }
            metadata_dict['attributes'].append(attributes_dict)

    with open(f'build/json/{edition}.json', 'w', encoding='utf-8') as outfile:
        json.dump(metadata_dict, outfile, indent=2)


def create_image(config_file: object, edition: int, final_layers: tuple) -> None:
    token_prefix = config_file['token_prefix']

    if config_file['draw_background']:
        width = config_file['canvas_width']
        height = config_file['canvas_height']
        bg_color = config_file['background_color']
        base_image = Image.new(mode='RGBA', size=(width, height), color=bg_color)
    else:
        base_image = Image.open(final_layers[0]).convert('RGBA')
        final_layers = final_layers[1:]

    for file in final_layers:
        if file != 'None':
            img = Image.open(file).convert('RGBA')
            base_image.alpha_composite(img)

    base_image.save(f'build/images/{edition}.png')


def run() -> None:
    """ Main collection creation function. Creates a build directory, 
    edition counter, then loops through for the desired amount. DNA set keeps track 
    of each created image to avoid duplicates being created."""

    config_file = read_yaml()
    dna_set = set()

    if config_file['id_from_one']:
        edition = 1
        desired_amount = config_file['amount'] + 1
    else:
        edition = 0
        desired_amount = config_file['amount']

    make_dirs()

    while edition < desired_amount:
        print(f'Creating token #{edition}')

        token_layers = join_layers(config_file)

        if token_layers not in dna_set:
            create_metadata(config_file, edition, token_layers)
            create_image(config_file, edition, token_layers)
            dna_set.add(token_layers)
            edition += 1
        else:
            print(f'Token #{edition} already exists, re-creating token')

    amount = config_file['amount']

    if config_file['rich_metadata']:

        if config_file['id_from_one']:
            edition = 1
            desired_amount = config_file['amount'] + 1
        else:
            edition = 0
            desired_amount = config_file['amount']

        counts = rm.create_counts(edition, amount)
        percentages = rm.calculate_percentages(amount, counts)
        rm.update_metadata(edition, amount, counts, percentages)

    if config_file['paintswap_metadata']:
        try:
            harmonic_means = rr.calculate_mean(amount, edition)
            rr.add_rarity_rank(harmonic_means)
        except FileNotFoundError:
            print("Cannot use paintswap metadata without rich_metadata!\n" 
            + "Please set it to true in the config file.")
