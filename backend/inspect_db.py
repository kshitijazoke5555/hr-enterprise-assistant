from sqlalchemy import create_engine
engine = create_engine('sqlite:///./chat_history.db', connect_args={'check_same_thread': False})
with engine.connect() as conn:
    res = conn.execute('PRAGMA table_info(messages);')
    rows = res.fetchall()
    print('columns:', [r[1] for r in rows])
