import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import markdown

load_dotenv()

from models import db, User, Repository, RepoFile, Star, Issue
from forms import (
    RegistrationForm, LoginForm, RepositoryForm, FileUploadForm, 
    IssueForm, ProfileEditForm, SearchForm
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'codeforge-default-secret-key-2026')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///codeforge.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

db.init_app(app)

with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database table initialization warning: {e}")

login_manager = LoginManager()

login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_search_form():
    return dict(search_form=SearchForm())

@app.template_filter('render_markdown')
def render_markdown_filter(text):
    if not text:
        return ""
    return markdown.markdown(text, extensions=['fenced_code', 'tables'])

# Helper function to check access to repository
def check_repo_access(repo):
    if repo.is_private:
        if not current_user.is_authenticated:
            return False
        if repo.owner_id != current_user.id and not current_user.is_admin:
            return False
    return True

# --- ROUTES ---

@app.route('/')
def home():
    public_repos = Repository.query.filter_by(is_private=False).order_by(Repository.created_at.desc()).limit(10).all()
    stats = {
        'total_users': User.query.count(),
        'total_repos': Repository.query.count(),
        'total_stars': Star.query.count()
    }
    return render_template('home.html', public_repos=public_repos, stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            bio=form.bio.data.strip() if form.bio.data else ''
        )
        user.set_password(form.password.data)
        
        # If this is the very first user, make them admin automatically
        if User.query.count() == 0:
            user.is_admin = True

        db.session.add(user)
        db.session.commit()
        
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    form = LoginForm()
    if form.validate_on_submit():
        login_input = form.login_id.data.strip()
        user = User.query.filter((User.username == login_input) | (User.email == login_input.lower())).first()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password. Please try again.', 'danger')
            
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    my_repos = Repository.query.filter_by(owner_id=current_user.id).order_by(Repository.created_at.desc()).all()
    starred_entries = Star.query.filter_by(user_id=current_user.id).all()
    starred_repos = [entry.repository for entry in starred_entries if entry.repository]
    
    return render_template('dashboard.html', my_repos=my_repos, starred_repos=starred_repos)

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Public repos or all repos if viewing own profile
    if current_user.is_authenticated and (current_user.id == user.id or current_user.is_admin):
        repos = Repository.query.filter_by(owner_id=user.id).order_by(Repository.created_at.desc()).all()
    else:
        repos = Repository.query.filter_by(owner_id=user.id, is_private=False).order_by(Repository.created_at.desc()).all()
        
    starred_entries = Star.query.filter_by(user_id=user.id).all()
    starred_repos = [entry.repository for entry in starred_entries if entry.repository and (not entry.repository.is_private or (current_user.is_authenticated and (entry.repository.owner_id == current_user.id or current_user.is_admin)))]
    
    form = ProfileEditForm(bio=user.bio)
    if form.validate_on_submit() and current_user.is_authenticated and current_user.id == user.id:
        user.bio = form.bio.data.strip()
        db.session.commit()
        flash('Profile bio updated successfully!', 'success')
        return redirect(url_for('profile', username=user.username))

    return render_template('profile.html', profile_user=user, repos=repos, starred_repos=starred_repos, form=form)

@app.route('/repo/new', methods=['GET', 'POST'])
@login_required
def create_repo():
    form = RepositoryForm()
    if form.validate_on_submit():
        # Check duplicate repo name for same user
        existing = Repository.query.filter_by(owner_id=current_user.id, name=form.name.data.strip()).first()
        if existing:
            flash('You already have a repository with this name. Please choose another name.', 'warning')
            return render_template('create_repo.html', form=form)
            
        repo = Repository(
            name=form.name.data.strip(),
            description=form.description.data.strip(),
            is_private=form.is_private.data,
            owner_id=current_user.id
        )
        db.session.add(repo)
        db.session.commit()
        
        # Create directory for uploads
        repo_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'repo_{repo.id}')
        os.makedirs(repo_upload_dir, exist_ok=True)
        
        flash(f'Repository "{repo.name}" created successfully!', 'success')
        return redirect(url_for('view_repo', repo_id=repo.id))
        
    return render_template('create_repo.html', form=form)

@app.route('/repo/<int:repo_id>')
def view_repo(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if not check_repo_access(repo):
        flash('This repository is private.', 'danger')
        return redirect(url_for('home'))
        
    readme_file = repo.get_readme()
    readme_content = None
    if readme_file:
        full_path = os.path.join(app.static_folder, readme_file.file_path.replace('static/', '', 1).replace('/', os.sep))
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    readme_content = f.read()
            except Exception:
                readme_content = "Failed to load README.md content."

    is_starred = current_user.is_authenticated and current_user.has_starred(repo.id)
    
    return render_template('repository.html', repo=repo, readme_file=readme_file, readme_content=readme_content, is_starred=is_starred)

@app.route('/repo/<int:repo_id>/upload', methods=['GET', 'POST'])
@login_required
def upload_file(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if repo.owner_id != current_user.id and not current_user.is_admin:
        flash('Permission denied. Only repository owner or admin can upload files.', 'danger')
        return redirect(url_for('view_repo', repo_id=repo.id))
        
    form = FileUploadForm()
    if form.validate_on_submit():
        file_data = form.file.data
        filename = secure_filename(file_data.filename)
        if not filename:
            flash('Invalid filename.', 'danger')
            return render_template('upload_file.html', form=form, repo=repo)
            
        repo_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'repo_{repo.id}')
        os.makedirs(repo_upload_dir, exist_ok=True)
        
        save_path = os.path.join(repo_upload_dir, filename)
        file_data.save(save_path)
        
        file_size = os.path.getsize(save_path)
        rel_path = f'uploads/repo_{repo.id}/{filename}'
        
        # Check if file already exists in DB
        existing_file = RepoFile.query.filter_by(repository_id=repo.id, filename=filename).first()
        if existing_file:
            existing_file.file_size = file_size
            existing_file.uploaded_at = datetime.utcnow()
            flash(f'File "{filename}" updated in repository!', 'success')
        else:
            new_file = RepoFile(
                filename=filename,
                file_path=rel_path,
                file_size=file_size,
                repository_id=repo.id
            )
            db.session.add(new_file)
            flash(f'File "{filename}" uploaded successfully!', 'success')
            
        db.session.commit()
        return redirect(url_for('view_repo', repo_id=repo.id))
        
    return render_template('upload_file.html', form=form, repo=repo)

@app.route('/repo/<int:repo_id>/file/<int:file_id>')
def view_file(repo_id, file_id):
    repo = Repository.query.get_or_404(repo_id)
    if not check_repo_access(repo):
        flash('This repository is private.', 'danger')
        return redirect(url_for('home'))
        
    file_record = RepoFile.query.get_or_404(file_id)
    if file_record.repository_id != repo.id:
        abort(404)
        
    full_path = os.path.join(app.static_folder, file_record.file_path)
    content = None
    is_binary = False
    
    if os.path.exists(full_path):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            is_binary = True
        except Exception as e:
            content = f"Error reading file: {str(e)}"
    else:
        content = "File missing from disk storage."

    lines = content.split('\n') if content is not None else []
    
    return render_template('file_view.html', repo=repo, file_record=file_record, content=content, lines=lines, is_binary=is_binary)

@app.route('/repo/<int:repo_id>/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(repo_id, file_id):
    repo = Repository.query.get_or_404(repo_id)
    if repo.owner_id != current_user.id and not current_user.is_admin:
        flash('Permission denied.', 'danger')
        return redirect(url_for('view_repo', repo_id=repo.id))
        
    file_record = RepoFile.query.get_or_404(file_id)
    if file_record.repository_id != repo.id:
        abort(404)
        
    full_path = os.path.join(app.static_folder, file_record.file_path)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except Exception:
            pass
            
    db.session.delete(file_record)
    db.session.commit()
    
    flash(f'File "{file_record.filename}" deleted.', 'info')
    return redirect(url_for('view_repo', repo_id=repo.id))

@app.route('/repo/<int:repo_id>/star', methods=['POST'])
@login_required
def toggle_star(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if not check_repo_access(repo):
        flash('Cannot star private repository.', 'danger')
        return redirect(url_for('home'))
        
    star = Star.query.filter_by(user_id=current_user.id, repository_id=repo.id).first()
    if star:
        db.session.delete(star)
        db.session.commit()
        flash(f'Unstarred "{repo.name}".', 'info')
    else:
        new_star = Star(user_id=current_user.id, repository_id=repo.id)
        db.session.add(new_star)
        db.session.commit()
        flash(f'Starred "{repo.name}"!', 'success')
        
    return redirect(url_for('view_repo', repo_id=repo.id))

@app.route('/repo/<int:repo_id>/issues', methods=['GET', 'POST'])
def view_issues(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if not check_repo_access(repo):
        flash('This repository is private.', 'danger')
        return redirect(url_for('home'))
        
    form = IssueForm()
    if form.validate_on_submit() and current_user.is_authenticated:
        issue = Issue(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            author_id=current_user.id,
            repository_id=repo.id
        )
        db.session.add(issue)
        db.session.commit()
        flash('New issue created successfully!', 'success')
        return redirect(url_for('view_issues', repo_id=repo.id))
        
    issues_list = Issue.query.filter_by(repository_id=repo.id).order_by(Issue.created_at.desc()).all()
    return render_template('issues.html', repo=repo, issues=issues_list, form=form)

@app.route('/repo/<int:repo_id>/issues/<int:issue_id>/close', methods=['POST'])
@login_required
def close_issue(repo_id, issue_id):
    repo = Repository.query.get_or_404(repo_id)
    issue = Issue.query.get_or_404(issue_id)
    
    if issue.repository_id != repo.id:
        abort(404)
        
    if current_user.id != repo.owner_id and current_user.id != issue.author_id and not current_user.is_admin:
        flash('Permission denied. Only repo owner, issue author, or admin can close this issue.', 'danger')
        return redirect(url_for('view_issues', repo_id=repo.id))
        
    issue.status = 'closed'
    issue.closed_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'Issue #{issue.id} has been closed.', 'info')
    return redirect(url_for('view_issues', repo_id=repo.id))

@app.route('/repo/<int:repo_id>/delete', methods=['POST'])
@login_required
def delete_repo(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if repo.owner_id != current_user.id and not current_user.is_admin:
        flash('Permission denied to delete repository.', 'danger')
        return redirect(url_for('view_repo', repo_id=repo.id))
        
    # Delete uploaded files folder from disk
    repo_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'repo_{repo.id}')
    if os.path.exists(repo_upload_dir):
        import shutil
        try:
            shutil.rmtree(repo_upload_dir)
        except Exception:
            pass
            
    db.session.delete(repo)
    db.session.commit()
    
    flash(f'Repository "{repo.name}" has been deleted.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/search')
def search():
    query = request.args.get('query', '').strip()
    results = []
    if query:
        # Search public repositories matching query in name or description
        results = Repository.query.filter(
            Repository.is_private == False,
            (Repository.name.ilike(f'%{query}%')) | (Repository.description.ilike(f'%{query}%'))
        ).order_by(Repository.created_at.desc()).all()
        
    return render_template('search.html', query=query, results=results)

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard'))
        
    users = User.query.order_by(User.created_at.desc()).all()
    repos = Repository.query.order_by(Repository.created_at.desc()).all()
    
    stats = {
        'total_users': len(users),
        'total_repos': len(repos),
        'total_stars': Star.query.count(),
        'total_issues': Issue.query.count()
    }
    
    return render_template('admin_dashboard.html', users=users, repos=repos, stats=stats)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
