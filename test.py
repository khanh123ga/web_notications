from sqlalchemy import create_engine, Column, String, Boolean, text

# Kết nối tới cơ sở dữ liệu
engine = create_engine('sqlite:///site.db')  # Thay 'your_database.db' bằng đường dẫn tới DB của bạn

def add_column(engine, table_name, column):
    column_name = column.name  # Tên của cột
    column_type = column.type.compile(dialect=engine.dialect)  # Loại cột (ví dụ: STRING, INTEGER)
    
    # Kết nối và thực thi câu lệnh ALTER TABLE
    with engine.connect() as connection:
        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))

# Định nghĩa cột mới
group_name_column = Column('group_name', String(150), nullable=True)
is_seen_column = Column('is_seen', Boolean, default=False)

# Thêm cột vào bảng notification_history
add_column(engine, 'notification_history', group_name_column)
add_column(engine, 'notification_history', is_seen_column)
