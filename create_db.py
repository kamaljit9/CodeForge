import os
from app import app
from models import db, User, Repository, RepoFile, Star, Issue

def init_database():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()

        # Check if admin exists
        admin = User.query.filter_by(email='admin@codeforge.com').first()
        if not admin:
            print("Seeding Admin User...")
            admin = User(
                username='admin',
                email='admin@codeforge.com',
                bio='Platform Administrator and System Maintainer.',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)

        # Check if demo user exists
        demo_user = User.query.filter_by(username='code_master').first()
        if not demo_user:
            print("Seeding Demo User...")
            demo_user = User(
                username='code_master',
                email='demo@codeforge.com',
                bio='Open source contributor and python developer.',
                is_admin=False
            )
            demo_user.set_password('demo1234')
            db.session.add(demo_user)

        db.session.commit()

        # Seed demo repository if no repo exists
        if Repository.query.count() == 0:
            print("Seeding Sample Repository...")
            sample_repo = Repository(
                name='flask-starter-template',
                description='A simple, robust boilerplate project for building web applications with Flask & SQLAlchemy.',
                is_private=False,
                owner_id=demo_user.id
            )
            db.session.add(sample_repo)
            db.session.commit()

            # Create upload dir for sample repo
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'repo_{sample_repo.id}')
            os.makedirs(upload_dir, exist_ok=True)

            # Create sample README.md
            readme_filename = 'README.md'
            readme_path = os.path.join(upload_dir, readme_filename)
            readme_content = """# Flask Starter Template

Welcome to **Flask Starter Template** hosted on **CodeForge**!

## Features
- Clean blueprint setup
- Integrated SQLAlchemy models
- Authentication & User Management
- Simple, dark aesthetic design

## Quick Start
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Happy coding!
"""
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)

            file_size = os.path.getsize(readme_path)
            readme_record = RepoFile(
                filename=readme_filename,
                file_path=f'uploads/repo_{sample_repo.id}/{readme_filename}',
                file_size=file_size,
                repository_id=sample_repo.id
            )
            db.session.add(readme_record)

            # Sample Python File
            py_filename = 'main.py'
            py_path = os.path.join(upload_dir, py_filename)
            py_content = """# Main Application Entrypoint

def hello_world():
    print("Welcome to CodeForge!")

if __name__ == "__main__":
    hello_world()
"""
            with open(py_path, 'w', encoding='utf-8') as f:
                f.write(py_content)

            py_record = RepoFile(
                filename=py_filename,
                file_path=f'uploads/repo_{sample_repo.id}/{py_filename}',
                file_size=os.path.getsize(py_path),
                repository_id=sample_repo.id
            )
            db.session.add(py_record)

            # Sample issue
            sample_issue = Issue(
                title='Add Docker Containerization',
                description='Please add a Dockerfile and docker-compose.yml to streamline local testing.',
                author_id=admin.id,
                repository_id=sample_repo.id
            )
            db.session.add(sample_issue)

            # Star demo repo by admin
            star = Star(user_id=admin.id, repository_id=sample_repo.id)
            db.session.add(star)

            db.session.commit()
            print("Sample Repository seeded successfully!")

        print("Database initialization complete.")

if __name__ == '__main__':
    init_database()
