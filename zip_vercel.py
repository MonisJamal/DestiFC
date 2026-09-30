import zipfile
import os

def create_vercel_zip():
    zipf = zipfile.ZipFile('destifc_vercel_admin.zip', 'w', zipfile.ZIP_DEFLATED)
    src_dir = 'vercel_admin'

    for root, dirs, files in os.walk(src_dir):
        if 'node_modules' in dirs:
            dirs.remove('node_modules')
        if '.next' in dirs:
            dirs.remove('.next')
        for file in files:
            if file.endswith('.DS_Store'):
                continue
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, src_dir)
            zipf.write(filepath, arcname)

    zipf.close()
    print("Vercel Admin zip created successfully!")

create_vercel_zip()
