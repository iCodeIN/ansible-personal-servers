CREATE DATABASE {{ matrix_server_db_user }}
  ENCODING 'UTF8'
  LC_COLLATE='C'
  LC_CTYPE='C'
  template=template0
  OWNER {{ matrix_server_db_user }};
