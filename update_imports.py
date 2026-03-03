import os
import glob

files = glob.glob('app/**/*.py', recursive=True)

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    new_content = content
    # Replace flashcards_share imports
    new_content = new_content.replace('app.controllers.flashcards_share', 'app.services.flashcards_share')
    new_content = new_content.replace('app.controllers import flashcards_share_controller as share_ctrl', 'app.services import flashcards_share')
    new_content = new_content.replace('share_ctrl.', 'flashcards_share.')
    new_content = new_content.replace('flashcards_share_controller', 'flashcards_share')
    
    # Replace marketplace imports
    new_content = new_content.replace('app.controllers import flashcards_marketplace_controller as marketplace_ctrl', 'app.services import marketplace_query_service')
    new_content = new_content.replace('app.controllers.flashcards_marketplace_controller', 'app.services.marketplace_query_service')
    new_content = new_content.replace('marketplace_ctrl.', 'marketplace_query_service.')
    new_content = new_content.replace('marketplace_ctrl', 'marketplace_query_service')
    
    if new_content != content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        print(f"Updated {f}")
