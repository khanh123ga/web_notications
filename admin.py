from app import app, db, User

# Create a new user inside the application context
with app.app_context():
    # Create a new user
    admin_user = User(username='admin1', email='admin@example.com')
    admin_user.set_password('admin')  # Set password for the admin

    # Set the is_admin flag to True
    admin_user.is_admin = True

    # Add to the database session and commit
    db.session.add(admin_user)
    db.session.commit()

    print("Admin user created successfully!")
