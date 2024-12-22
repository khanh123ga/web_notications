from flask import Flask, render_template, redirect, url_for, flash, request, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from zoneinfo import ZoneInfo
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '11111'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}  # Tùy chỉnh theo loại tệp bạn muốn hỗ trợ

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Define the user_group association table
user_group = db.Table('user_group',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

# Define the user_notification association table
user_notification = db.Table('user_notification',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('notification_id', db.Integer, db.ForeignKey('notification.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    groups = db.relationship('Group', secondary=user_group, backref='members')
    notifications = db.relationship('Notification', secondary=user_notification, backref='notification_recipients')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def get_vietnam_time():
    return datetime.now(tz=ZoneInfo("Asia/Ho_Chi_Minh"))
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Đảm bảo có cột này
    user = db.relationship('User', backref=db.backref('user_notifications', lazy=True))
    file_name = db.Column(db.String(100))  # Lưu tên tệp
    date_created = db.Column(db.DateTime, default=get_vietnam_time)  # Lưu ngày giờ tạo

class NotificationHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('notification.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    date_sent = db.Column(db.DateTime, default=get_vietnam_time)
    is_seen = db.Column(db.Boolean, default=False)
    notification = db.relationship('Notification', backref='history')
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_notifications')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_notifications')
    group = db.relationship('Group', back_populates='notifications')
    
    def mark_as_seen(self):
        self.is_seen = True
        db.session.commit()

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    users = db.relationship('User', secondary=user_group, backref=db.backref('user_groups', lazy='dynamic'))
     # Định nghĩa quan hệ ngược với bảng NotificationHistory
    notifications = db.relationship('NotificationHistory', back_populates='group')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    # Sắp xếp thông báo theo thời gian giảm dần
    notifications = sorted(current_user.notifications, key=lambda n: n.date_created, reverse=True)
    return render_template('index.html', notifications=notifications)

@app.route('/index')
def home():
    if current_user.is_authenticated:
        # Sắp xếp các thông báo theo thời gian giảm dần
        notifications = sorted(current_user.notifications, key=lambda n: n.date_created, reverse=True)
        return render_template('index.html', notifications=notifications)
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('User registered successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/manage_users')
@login_required
def manage_users():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    user = User.query.get(user_id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        if request.form['password']:
            user.password_hash = generate_password_hash(request.form['password'])
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('manage_users'))
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('manage_users'))

@app.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        selected_users = request.form.getlist('members')  # Nhận danh sách người dùng được chọn

        # Tạo nhóm mới
        new_group = Group(name=name)
        db.session.add(new_group)
        db.session.commit()

        # Thêm người dùng vào nhóm
        for user_id in selected_users:
            user = User.query.get(user_id)
            new_group.users.append(user)

        db.session.commit()
        flash('Group created successfully!', 'success')
        return redirect(url_for('manage_groups'))

    # Lấy danh sách người dùng để hiển thị
    users = User.query.all()
    return render_template('create_group.html', users=users)


@app.route('/manage_groups')
@login_required
def manage_groups():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    groups = Group.query.all()
    return render_template('manage_groups.html', groups=groups)

@app.route('/view_group/<int:group_id>', methods=['GET'])
@login_required
def view_group(group_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    group = Group.query.get(group_id)
    return render_template('view_group.html', group=group)

@app.route('/edit_group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    group = Group.query.get(group_id)
    if request.method == 'POST':
        group.name = request.form['name']
        # Thêm hoặc xóa thành viên
        selected_users = request.form.getlist('members')  # Nhận danh sách người dùng được chọn
        # Cập nhật danh sách thành viên
        current_members = set(user.id for user in group.users)
        new_members = set(selected_users)
        
        # Thêm người dùng mới vào nhóm
        for user_id in new_members - current_members:
            user = User.query.get(user_id)
            group.users.append(user)
        
        # Xóa người dùng khỏi nhóm
        for user_id in current_members - new_members:
            user = User.query.get(user_id)
            group.users.remove(user)

        db.session.commit()
        flash('Group updated successfully!', 'success')
        return redirect(url_for('manage_groups'))
    
    # Lấy danh sách người dùng để hiển thị
    users = User.query.all()
    return render_template('edit_group.html', group=group, users=users)


@app.route('/remove_user_from_group/<int:group_id>/<int:user_id>', methods=['POST'])
@login_required
def remove_user_from_group(group_id, user_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))

    group = Group.query.get(group_id)
    user = User.query.get(user_id)
    
    if group and user:
        if user in group.users:
            group.users.remove(user)
            db.session.commit()
            flash(f'User {user.username} removed from group {group.name} successfully!', 'success')
        else:
            flash(f'User {user.username} is not a member of this group.', 'danger')
    else:
        flash('Group or User not found.', 'danger')

    return redirect(url_for('edit_group', group_id=group.id))

@app.route('/add_user_to_group/<int:group_id>', methods=['POST'])
@login_required
def add_user_to_group(group_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))

    group = Group.query.get(group_id)
    user_id = request.form.get('user_id')  # ID của người dùng được chọn để thêm vào nhóm
    user = User.query.get(user_id)

    if group and user:
        if user not in group.users:
            group.users.append(user)
            db.session.commit()
            flash(f'User {user.username} added to group {group.name} successfully!', 'success')
        else:
            flash(f'User {user.username} is already a member of this group.', 'warning')
    else:
        flash('Group or User not found.', 'danger')

    return redirect(url_for('edit_group', group_id=group.id))

@app.route('/delete_group/<int:group_id>', methods=['POST'])
@login_required
def delete_group(group_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))

    # Tìm nhóm trong cơ sở dữ liệu
    group = Group.query.get(group_id)
    
    # Kiểm tra xem nhóm có tồn tại hay không
    if group:
        # Xóa các bản ghi liên quan trong bảng phụ user_group trước
        db.session.query(user_group).filter_by(group_id=group_id).delete(synchronize_session='fetch')

        # Xóa nhóm
        db.session.delete(group)
        db.session.commit()

        flash(f'Group "{group.name}" deleted successfully!', 'success')
    else:
        flash('Group not found.', 'danger')

    return redirect(url_for('manage_groups'))

'''---------------------------------------------------------------------------------------------------------------------------------------------------------------'''



@app.route('/history_notification', methods=['GET', 'POST'])
@login_required
def create_notification():
    if request.method == 'POST':
        content = request.form['content']
        notification_type = request.form['type']
        category = request.form['category']
        file = request.files['file']
        
        # Lưu tệp vào thư mục tạm
        if file:
            file_name = file.filename
            file.save(f'uploads/{file_name}')  # Lưu tệp tin vào thư mục uploads
        else:
            file_name = None

        new_notification = Notification(
            content=content,
            type=notification_type,
            category=category,
            user=current_user,
            file_name=file_name
        )
        db.session.add(new_notification)
        db.session.commit()
        flash('Notification created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('history_notification.html')

@app.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/send_notification_to_user', methods=['GET', 'POST'])
@login_required
def send_notification_to_user():
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        user_ids = request.form.getlist('user_ids')  # Lấy danh sách người dùng đã chọn
        file = request.files.get('file')  # Lấy tệp đính kèm (nếu có)
        
        # Kiểm tra nếu không có người dùng nào được chọn
        if not user_ids:
            flash('No users selected!', 'danger')
            return redirect(url_for('send_notification_to_user'))

        # Lưu tệp nếu có
        file_name = None
        if file:
            # Kiểm tra nếu thư mục uploads không tồn tại
            upload_folder = 'uploads'
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            file_name = file.filename
            file.save(os.path.join(upload_folder, file_name))  # Lưu tệp tin vào thư mục uploads
        
        # Tạo thông báo mới
        new_notification = Notification(
            type=title,
            content=content,
            category=category,
            file_name=file_name,
            user=current_user  # Gán user_id của người gửi
        )
        
        try:
            db.session.add(new_notification)
            db.session.commit()

            
            # Gửi thông báo tới những người dùng đã chọn
            users = User.query.filter(User.id.in_(user_ids)).all()
            for user in users:
                # Thêm thông báo vào bảng liên kết giữa User và Notification
                user.notifications.append(new_notification)  # Liên kết người dùng với thông báo
                db.session.flush()  # Đảm bảo rằng sự thay đổi được ghi lại trước khi commit

                # Lưu lịch sử gửi thông báo vào bảng NotificationHistory
                history = NotificationHistory(
                    notification_id=new_notification.id,
                    sender_id=current_user.id,  # Người gửi là người hiện tại
                    recipient_id=user.id,  # Người nhận
                    date_sent=datetime.utcnow()  # Thời gian gửi
                )
                db.session.add(history)
            db.session.commit()
            flash('Notification sent to selected users!', 'success')
        except Exception as e:
            db.session.rollback()  # Nếu có lỗi, rollback lại các thay đổi
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('send_notification_to_user'))

        return redirect(url_for('index'))

    users = User.query.all()
    return render_template('send_notification_to_user.html', users=users)


@app.route('/send_notification_to_group', methods=['GET', 'POST'])
@login_required
def send_notification_to_group():
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        type = request.form['title']
        content = request.form['content']
        notification_type = request.form['category']  # Loại thông báo (có thể được tùy chỉnh thêm)
        group_ids = request.form.getlist('group_ids')  # Lấy danh sách nhóm đã chọn
        file = request.files.get('file')  # Lấy tệp đính kèm (nếu có)
        
        # Lưu tệp nếu có
        file_name = None
        if file:
            file_name = file.filename
            file.save(f'uploads/{file_name}')  # Lưu tệp vào thư mục uploads

        # Tạo thông báo mới
        new_notification = Notification(
            type=type,
            category=notification_type, 
            content=content,
            file_name=file_name,
            user=current_user  # Thêm người tạo thông báo
        )

        db.session.add(new_notification)
        db.session.commit()

        # Gửi thông báo tới các nhóm đã chọn và ghi lại lịch sử thông báo
        for group_id in group_ids:
            group = Group.query.get(group_id)  # Lấy nhóm
            for user in group.users:  # Lấy tất cả thành viên trong nhóm
                user.notifications.append(new_notification)  # Thêm thông báo cho người dùng

            # Lưu lịch sử gửi thông báo cho nhóm
            history_entry = NotificationHistory(
                notification=new_notification,
                group_id = group.id,  # Lưu tên nhóm thay vì tên người nhận
                date_sent=datetime.utcnow(),
                sender=current_user
            )
            db.session.add(history_entry)

        db.session.commit()
        flash('Notification created and sent to selected groups!', 'success')
        return redirect(url_for('send_notification_to_group'))

    # Hiển thị form gửi thông báo
    groups = Group.query.all()  # Lấy tất cả các nhóm
    return render_template('send_notification_to_group.html', groups=groups)

'''----------------------------------------------------------------------------------------------------------------------------------------------------'''
@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found.', 'danger')
        return redirect(url_for('index'))
    
    
'''-------------------------------------------------------------'''
@app.route('/sent_notifications')
@login_required
def sent_notifications():
    # Truy vấn các thông báo đã gửi của người dùng hiện tại
    sent_notifications = NotificationHistory.query.filter_by(sender_id=current_user.id).all()
    
    return render_template('history_notification.html', sent_notifications=sent_notifications)


'''----------------------------------------------------------------------'''
@app.route('/mark_as_seen/<int:notification_id>', methods=['POST'])
@login_required
def mark_as_seen(notification_id):
    # Tìm lịch sử thông báo theo ID và kiểm tra nếu người dùng là người nhận
    notification_history = NotificationHistory.query.filter_by(
        notification_id=notification_id, recipient_id=current_user.id, is_seen=False).first()

    if notification_history:
        # Đánh dấu thông báo là đã đọc
        notification_history.mark_as_seen()
        flash('Notification marked as read.', 'success')
    else:
        flash('Notification not found or already read.', 'danger')

    return redirect(url_for('index'))

'''-----------------------------------------------'''
@app.route('/delete_notification/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    # Kiểm tra quyền của người dùng (người gửi mới có quyền xóa)
    if notification.user_id != current_user.id:
        flash("You are not authorized to delete this notification.", "danger")
        return redirect(url_for('index'))

    # Xóa tất cả lịch sử liên quan đến thông báo này
    NotificationHistory.query.filter_by(notification_id=notification_id).delete()

    # Xóa thông báo
    db.session.delete(notification)
    db.session.commit()

    flash("Notification deleted successfully.", "success")
    return redirect(url_for('index'))
'''-----------------------------------------------'''
@app.route('/search_notifications', methods=['GET'])
@login_required
def search_notifications():
    search_query = request.args.get('search')  # Get the search query from the URL
    
    # If a search query is provided, filter notifications based on the content or other fields
    if search_query:
        notifications = Notification.query.filter(
            Notification.content.like(f'%{search_query}%') |
            Notification.type.like(f'%{search_query}%') |
            Notification.category.like(f'%{search_query}%')
        ).all()
    else:
        # If no search query is provided, show all notifications
        notifications = Notification.query.all()

    return render_template('history_notification.html', notifications=notifications)

if __name__ == '__main__':
    #with app.app_context():
        #db.drop_all() 
        #db.create_all()
    app.run(debug=True)
