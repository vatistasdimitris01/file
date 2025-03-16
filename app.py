from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file, jsonify
import os
import shutil
import zipfile
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Define the shared folder path
SHARED_FOLDER = r'G:\HomeCloud'  # Using raw string to handle Windows path
if not os.path.exists(SHARED_FOLDER):
    os.makedirs(SHARED_FOLDER)

@app.route('/')
def index():
    files = []
    for item in os.listdir(SHARED_FOLDER):
        item_path = os.path.join(SHARED_FOLDER, item)
        is_dir = os.path.isdir(item_path)
        files.append({
            'name': item,
            'path': item,
            'is_dir': is_dir
        })
    
    all_folders = get_all_folders()
    return render_template('index.html', files=files, current_path='', all_folders=all_folders)

@app.route('/browse/<path:folder_path>')
def browse_folder(folder_path):
    full_path = os.path.join(SHARED_FOLDER, folder_path)
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        return redirect(url_for('index'))
    
    files = []
    for item in os.listdir(full_path):
        item_path = os.path.join(folder_path, item)
        full_item_path = os.path.join(SHARED_FOLDER, item_path)
        is_dir = os.path.isdir(full_item_path)
        files.append({
            'name': item,
            'path': item_path,
            'is_dir': is_dir
        })
    
    all_folders = get_all_folders()
    return render_template('index.html', files=files, current_path=folder_path, all_folders=all_folders)

def get_all_folders():
    folders = []
    
    def scan_folders(path, rel_path=''):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                rel_item_path = os.path.join(rel_path, item) if rel_path else item
                display_name = rel_item_path.replace('/', ' > ')
                folders.append({
                    'path': rel_item_path,
                    'display_name': display_name
                })
                scan_folders(item_path, rel_item_path)
    
    scan_folders(SHARED_FOLDER)
    return folders

@app.route('/preview/<path:filename>')
def preview(filename):
    file_path = os.path.join(SHARED_FOLDER, filename)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        return redirect(url_for('index'))
    
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Handle different file types
    if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
        file_type = 'image'
    elif file_ext in ['.mp4', '.webm', '.ogg']:
        file_type = 'video'
    elif file_ext in ['.mp3', '.wav']:
        file_type = 'audio'
    elif file_ext in ['.pdf']:
        file_type = 'pdf'
    elif file_ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.css', '.js', '.py']:
        file_type = 'text'
    else:
        file_type = 'unknown'
    
    return render_template('preview.html', filename=filename, file_type=file_type)

@app.route('/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(SHARED_FOLDER, filename)

@app.route('/download/<path:filename>')
def download_file(filename):
    file_path = os.path.join(SHARED_FOLDER, filename)
    
    # If it's a directory, create a zip file
    if os.path.isdir(file_path):
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(file_path):
                for file in files:
                    file_full_path = os.path.join(root, file)
                    zipf.write(
                        file_full_path, 
                        os.path.relpath(file_full_path, os.path.join(file_path, '..'))
                    )
        
        memory_file.seek(0)
        folder_name = os.path.basename(file_path)
        return send_from_directory(
            directory=os.path.dirname(file_path),
            path=os.path.basename(file_path),
            as_attachment=True,
            download_name=f"{folder_name}.zip",
            mimetype='application/zip'
        )
    
    # If it's a file, send it directly
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory=directory, path=filename, as_attachment=True)

@app.route('/bulk-download', methods=['POST'])
def bulk_download():
    filenames = request.form.get('filenames', '[]')
    import json
    file_paths = json.loads(filenames)
    
    if not file_paths:
        return redirect(url_for('index'))
    
    # Create a zip file in memory
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in file_paths:
            full_path = os.path.join(SHARED_FOLDER, file_path)
            
            if os.path.isdir(full_path):
                # Add all files in the directory
                for root, dirs, files in os.walk(full_path):
                    for file in files:
                        file_full_path = os.path.join(root, file)
                        zipf.write(
                            file_full_path, 
                            os.path.relpath(file_full_path, SHARED_FOLDER)
                        )
            else:
                # Add the individual file
                zipf.write(full_path, file_path)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='selected_files.zip'
    )


@app.route('/create-folder', methods=['POST'])
def create_folder():
    folder_name = request.form['folder_name']
    current_path = request.form.get('current_path', '')
    
    if current_path:
        folder_path = os.path.join(SHARED_FOLDER, current_path, folder_name)
        redirect_url = url_for('browse_folder', folder_path=current_path)
    else:
        folder_path = os.path.join(SHARED_FOLDER, folder_name)
        redirect_url = url_for('index')
    
    os.makedirs(folder_path, exist_ok=True)
    return redirect(redirect_url)

@app.route('/upload-file', methods=['POST'])
def upload_file():
    current_path = request.form.get('current_path', '')
    
    if 'file' not in request.files:
        return redirect(url_for('index'))
    
    files = request.files.getlist('file')
    
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            if current_path:
                file_path = os.path.join(SHARED_FOLDER, current_path, filename)
                redirect_url = url_for('browse_folder', folder_path=current_path)
            else:
                file_path = os.path.join(SHARED_FOLDER, filename)
                redirect_url = url_for('index')
            
            file.save(file_path)
    
    return redirect(redirect_url)

@app.route('/delete-file/<path:filename>', methods=['POST'])
def delete_file(filename):
    file_path = os.path.join(SHARED_FOLDER, filename)
    parent_dir = os.path.dirname(filename)
    
    if os.path.exists(file_path):
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
    
    if parent_dir:
        return redirect(url_for('browse_folder', folder_path=parent_dir))
    else:
        return redirect(url_for('index'))

@app.route('/bulk-delete', methods=['POST'])
def bulk_delete():
    filenames = request.form.get('filenames', '[]')
    import json
    file_paths = json.loads(filenames)
    
    if not file_paths:
        return redirect(url_for('index'))
    
    # Get the parent directory of the first file to redirect back to
    parent_dir = os.path.dirname(file_paths[0]) if file_paths else ''
    
    for file_path in file_paths:
        full_path = os.path.join(SHARED_FOLDER, file_path)
        if os.path.exists(full_path):
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
    
    if parent_dir:
        return redirect(url_for('browse_folder', folder_path=parent_dir))
    else:
        return redirect(url_for('index'))

@app.route('/edit-name/<path:filename>')
def edit_name(filename):
    file_path = os.path.join(SHARED_FOLDER, filename)
    if not os.path.exists(file_path):
        return redirect(url_for('index'))
    
    parent_dir = os.path.dirname(filename)
    file_name = os.path.basename(filename)
    
    return render_template('rename.html', filename=filename, file_name=file_name, parent_dir=parent_dir)

@app.route('/rename-file', methods=['POST'])
def rename_file():
    old_filename = request.form['old_filename']
    new_filename = request.form['new_filename']
    
    old_path = os.path.join(SHARED_FOLDER, old_filename)
    
    parent_dir = os.path.dirname(old_filename)
    if parent_dir:
        new_path = os.path.join(SHARED_FOLDER, parent_dir, new_filename)
        redirect_url = url_for('browse_folder', folder_path=parent_dir)
    else:
        new_path = os.path.join(SHARED_FOLDER, new_filename)
        redirect_url = url_for('index')
    
    if os.path.exists(old_path) and not os.path.exists(new_path):
        os.rename(old_path, new_path)
    
    return redirect(redirect_url)

@app.route('/move-file', methods=['POST'])
def move_file():
    filename = request.form['filename']
    destination = request.form['destination']
    
    source_path = os.path.join(SHARED_FOLDER, filename)
    file_name = os.path.basename(filename)
    
    if destination == '/':
        dest_path = os.path.join(SHARED_FOLDER, file_name)
        redirect_url = url_for('index')
    else:
        dest_path = os.path.join(SHARED_FOLDER, destination, file_name)
        redirect_url = url_for('browse_folder', folder_path=destination)
    
    if os.path.exists(source_path) and not os.path.exists(dest_path):
        if os.path.isdir(source_path):
            shutil.copytree(source_path, dest_path)
            shutil.rmtree(source_path)
        else:
            shutil.move(source_path, dest_path)
    
    parent_dir = os.path.dirname(filename)
    if parent_dir:
        return redirect(url_for('browse_folder', folder_path=parent_dir))
    else:
        return redirect(url_for('index'))

@app.route('/bulk-move', methods=['POST'])
def bulk_move():
    filenames = request.form.get('filenames', '[]')
    destination = request.form['destination']
    
    import json
    file_paths = json.loads(filenames)
    
    if not file_paths:
        return redirect(url_for('index'))
    
    # Get the parent directory of the first file to redirect back to
    parent_dir = os.path.dirname(file_paths[0]) if file_paths else ''
    
    for file_path in file_paths:
        source_path = os.path.join(SHARED_FOLDER, file_path)
        file_name = os.path.basename(file_path)
        
        if destination == '/':
            dest_path = os.path.join(SHARED_FOLDER, file_name)
        else:
            dest_path = os.path.join(SHARED_FOLDER, destination, file_name)
        
        if os.path.exists(source_path) and not os.path.exists(dest_path):
            if os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path)
                shutil.rmtree(source_path)
            else:
                shutil.move(source_path, dest_path)
    
    if parent_dir:
        return redirect(url_for('browse_folder', folder_path=parent_dir))
    else:
        return redirect(url_for('index'))

@app.route('/move-to-main', methods=['POST'])
def move_to_main():
    filename = request.form.get('filename', '')
    if not filename:
        return redirect(url_for('index'))
    
    source_path = os.path.join(SHARED_FOLDER, filename)
    file_name = os.path.basename(filename)
    dest_path = os.path.join(SHARED_FOLDER, file_name)
    
    parent_dir = os.path.dirname(filename)
    
    if os.path.exists(source_path) and not os.path.exists(dest_path):
        if os.path.isdir(source_path):
            shutil.copytree(source_path, dest_path)
            shutil.rmtree(source_path)
        else:
            shutil.move(source_path, dest_path)
    
    if parent_dir:
        return redirect(url_for('browse_folder', folder_path=parent_dir))
    else:
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
