import mysql.connector


class Utils:

    @classmethod
    def test_connection(cls,
                        db_name: str,
                        db_host: str,
                        db_port: int,
                        db_user: str,
                        db_password: str):
        success = False
        try:
            test_conn = mysql.connector.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                database=db_name,
                port=db_port
            )
            if test_conn.is_connected():
                print(f'MySQL Connection successful')
                success = True
        except mysql.connector.Error as e:
            print(f'MySQL Connection test failed: {e}')
        finally:
            if 'test_conn' in locals() and test_conn.is_connected():
                test_conn.close()

        return success