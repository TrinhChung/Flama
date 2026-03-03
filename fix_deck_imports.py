import glob
files = glob.glob('app/**/*.py', recursive=True)
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    new_content = content.replace('app.controllers.deck_controller', 'app.repositories.deck_tree_query')
    if new_content != content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
