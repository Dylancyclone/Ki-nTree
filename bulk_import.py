import os
import sys

import kintree.config.settings as settings
from kintree.common.tools import cprint, create_library, download_image
from kintree.config import config_interface
from kintree.database import inventree_api, inventree_interface
from kintree.kicad import kicad_interface
from kintree.search import digikey_api, mouser_api, lcsc_api
from kintree.search.snapeda_api import test_snapeda_api
from kintree.setup_inventree import setup_inventree

# SETTINGS
# Enable InvenTree import
ENABLE_INVENTREE = True
# Enable deletion
ENABLE_DELETE = False
AUTO_DELETE = False


# Pretty test printing
def pretty_test_print(message: str):
    cprint(message.ljust(65), end='')


# Check result
def check_result(status: str, new_part: bool) -> bool:
    # Build result
    success = False
    if (status == 'original') or (status == 'fake_alternate'):
        if new_part:
            success = True
    elif status == 'alternate_mpn':
        if not new_part:
            success = True
    else:
        pass

    return success


# --- SETUP ---

# Enable test mode
settings.enable_test_mode()
# Enable InvenTree
settings.set_inventree_enable_flag(True, save=True)
# Disable KiCad
settings.set_kicad_enable_flag(False, save=True)
# Load user configuration files
settings.load_user_config()
# Disable Digi-Key API logging
digikey_api.disable_api_logger()

# Test Digi-Key API
pretty_test_print('[MAIN]\tDigi-Key API Test')
if not digikey_api.test_api_connect(check_content=True):
    cprint('[ FAIL ]')
    cprint('[INFO]\tFailed to get Digi-Key API token, aborting.')
    sys.exit(-1)
else:
    cprint('[ PASS ]')

# Test Mouser API
pretty_test_print('[MAIN]\tMouser API Test')
if not mouser_api.test_api():
    cprint('[ FAIL ]')
    sys.exit(-1)
else:
    cprint('[ PASS ]')

# Test LCSC API
pretty_test_print('[MAIN]\tLCSC API Test')
if not lcsc_api.test_api():
    cprint('[ FAIL ]')
    sys.exit(-1)
else:
    cprint('[ PASS ]')

# Setup InvenTree
cprint('\n-----')
# setup_inventree()
cprint('\n-----')

# Load parts
samples = config_interface.load_file(os.path.abspath(
    os.path.join('bulk_import.yaml')))
PARTS = samples['Parts']

# Store results
exit_code = 0
inventree_results = {}

# --- TESTS ---
if __name__ == '__main__':
    if ENABLE_INVENTREE:
        pretty_test_print('\n[MAIN]\tConnecting to Inventree')
        inventree_connect = inventree_interface.connect_to_server()
        if inventree_connect:
            cprint('[ PASS ]')
        else:
            cprint('[ FAIL ]')
            sys.exit(-1)

        cprint(f'\n[MAIN]\tImporting Parts')

        for number, status in PARTS.items():
            inventree_result = False
            # Fetch supplier data
            part_info = inventree_interface.supplier_search(supplier='Digi-Key', part_number=number)
            # Translate to form
            part_form = inventree_interface.translate_supplier_to_form(supplier='Digi-Key', part_info=part_info)
            # Stitch categories and parameters
            part_form.update({
                'category': part_info['category'],
                'subcategory': part_info['subcategory'],
                'parameters': part_info['parameters'],
            })
            # Reset part info
            part_info = part_form
            # Display part to be tested
            pretty_test_print(f'[INFO]\tChecking "{number}" ({status})')

            if ENABLE_INVENTREE:
                # Adding part information to InvenTree
                categories = [None, None]
                new_part = False
                part_pk = 0
                part_data = {}

                # Get categories
                if part_info:
                    categories = inventree_interface.get_categories(part_info)

                # Create part in InvenTree
                if categories[0] and categories[1]:
                    new_part, part_pk, part_data = inventree_interface.inventree_create(part_info=part_info,
                                                                                        categories=categories,
                                                                                        show_progress=False)

                inventree_result = check_result(status, new_part)
                pk_list = [data[0] for data in inventree_results.values()]

                if part_pk != 0 and part_pk not in pk_list:
                    delete = True
                else:
                    delete = False

                # Log results
                inventree_results.update({number: [part_pk, inventree_result, delete]})

            result = inventree_result

            # Print live results
            if result:
                cprint('[ PASS ]')
            else:
                cprint('[ FAIL ]')
                exit_code = -1
                if ENABLE_INVENTREE:
                    cprint(f'[DBUG]\tinventree_result = {inventree_result}')
                    cprint(f'[DBUG]\tnew_part = {new_part}')
                    cprint(f'[DBUG]\tpart_pk = {part_pk}')

    if ENABLE_DELETE:
        if inventree_results:
            if not AUTO_DELETE:
                input('\nPress "Enter" to delete parts...')
            else:
                cprint('')

            if ENABLE_INVENTREE:
                error = 0

                pretty_test_print('[MAIN]\tDeleting InvenTree test parts')
                # Delete all InvenTree test parts
                for number, result in inventree_results.items():
                    if result[2]:
                        try:
                            if not inventree_api.delete_part(part_id=result[0]):
                                error += 1
                        except:
                            error += 1

                if error > 0:
                    cprint('[ FAIL ]')
                    exit_code = -1
                else:
                    cprint('[ PASS ]')

    sys.exit(exit_code)
