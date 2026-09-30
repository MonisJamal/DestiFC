import zipfile
import os

def create_zip():
    zipf = zipfile.ZipFile('destifc_deploy.zip', 'w', zipfile.ZIP_DEFLATED)
    
    ignore_dirs = {'.venv', '__pycache__', '.archive_scratch', '.git', 'test_images', 'brain', 'vercel_admin', 'admin_portal', 'web_admin', '.next', 'node_modules'}
    ignore_files = {'.env', 'destifc.db', 'destifc_deploy.zip', 'destifc_vercel_admin.zip', 'zip_project.py', 'zip_vercel.py', '.DS_Store'}
    ignore_exts = {'.pyc'}

    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if file in ignore_files or any(file.endswith(ext) for ext in ignore_exts):
                continue
            
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, '.')
            zipf.write(filepath, arcname)
            
    zipf.close()
    print("Zip created successfully.")

create_zip()
