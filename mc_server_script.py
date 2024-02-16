import subprocess
import threading
import datetime
import shutil
import time
import os

# Start the Minecraft server as a subprocess
server_jar = 'server.jar' # <-- change this to the name of your server jar
minecraft_server_process = subprocess.Popen(['java', 
                                             '-jar', 
                                             server_jar,
                                             'nogui'],
                                             stdin=subprocess.PIPE, 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE, 
                                             universal_newlines=True)
 
# Class that represents settings for backup such as time between backups
class BackupSettings:
    def __init__(self) -> None:
        self.time_between_backups = 24 * 60 * MINUTE
        self.zip_world = True

    def set_time_between_backups(self, tbb: str) -> None:
        self.time_between_backups = tbb

    def set_zip(self, b: bool) -> None:
        self.zip_world = b

# Variables running threads
exit_event = threading.Event()
MINUTE = 60 # constant for backup calculation
super_users = []
backup_settings = BackupSettings()

# Handles commands send from the terminal or from super user
def handle_user_commands(command: str) -> None:
    if command.startswith('!su '):
        name = command[4:].upper()

        if name in super_users:
            print('User is already a super user')
        else:
            super_users.append(name)

    elif command.startswith('!list'):
        print('Super users:')
        for su in super_users:
            print(su)

    elif command.startswith('!tbb '):
        tbb = int(command[5:])
        backup_settings.set_time_between_backups(tbb * MINUTE)
        message = f'Time between backups set to: {backup_settings.time_between_backups} seconds'
        send_command(minecraft_server_process, f'/say {message}')
        print(message)
            
    elif command.startswith('!tbbs '):
        tbb = int(command[6:])
        backup_settings.set_time_between_backups(tbb)
        message = f'Time between backups set to: {backup_settings.time_between_backups} seconds'
        send_command(minecraft_server_process, f'/say {message}')
        print(message)

    elif command.startswith('!bu'):
        backup_world()

    return

# Sends input to mc server process
def send_command(p, user_command: str) -> None:
    p.stdin.write(user_command + '\n')
    p.stdin.flush()

# Function for user input thread
def user_input_thread():
    while True:
        try:
            user_input = input()

            if exit_event.is_set():
                break

            if user_input.upper() == 'Q':
                break
            elif user_input.startswith('!'):
                handle_user_commands(user_input)
            else:
                send_command(minecraft_server_process, user_input)

        except EOFError:
            break

    print('closing user input thread')

input_thread = threading.Thread(target=user_input_thread)
input_thread.start()

# Finds the size of a directory
def find_dir_size(dir_name: str) -> int:
    size = 0

    with os.scandir(dir_name) as it:
        for entry in it:
            if entry.is_file():
                size += entry.stat().st_size
            elif entry.is_dir():
                size += find_dir_size(entry.path)
    
    return size

# Create backup world
def backup_world():
    curr_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir_name = 'world_' + curr_time
    dst_dir = os.path.join('./world_backups', backup_dir_name)

    if not os.path.exists('./world_backups'):
        os.makedirs('./world_backups')
        print('Created \'./world_backups\' directory')
    
    try:
        _, _ = minecraft_server_process.communicate(timeout=60)

        shutil.copytree('./world',
                        dst_dir,
                        ignore=shutil.ignore_patterns('*.lock'))
        
        world_size = find_dir_size(dst_dir)
        bu_msg = f'World backed up on: {curr_time}, current world size: {world_size}'
        send_command(minecraft_server_process, f'/say {bu_msg}')
        print(f"Backup completed")

        if backup_settings.zip_world:
            zip_dir = dst_dir + '_zipped'
            shutil.make_archive(zip_dir, 'zip', dst_dir)
            zipped_world_size = os.path.getsize(zip_dir + '.zip')
            saved_space = round(zipped_world_size / world_size * 100, 0)
            print(f'Zipped world backup, now taking up {saved_space}% amount of original space')

            try:
                shutil.rmtree(dst_dir)
            except OSError as e:
                print(f"Backup zipping failed. An error occurred: {e}")

    except Exception as e:
        print(f"Backup failed. An error occurred: {e}")
        send_command(minecraft_server_process, '/say World backup failed')

# Function for backup thread
def check_backup_thread():
    last_backup_time = time.time()

    while True:
        if (time.time() - last_backup_time) >= backup_settings.time_between_backups:
            backup_world()
            last_backup_time = time.time()
            time.sleep(10)

        if exit_event.is_set():
            break

    print('closing world backup thread')

backup_thread = threading.Thread(target=check_backup_thread)
backup_thread.start()

# Write process output to a txt file
def write_output_to_txt(curr_date, output: str) -> None:
    logs_dir = './world_backups/logs'

    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print('Created \'./world_backups/logs\' directory')

    curr_date = datetime.datetime.now().strftime('%Y-%m-%d')
    txt_name = curr_date + '_logs.txt'
    txt_dir = os.path.join(logs_dir, txt_name)

    with open(txt_dir, 'a') as f:
        f.write(output)

    return

# Read the output of the server
try:
    while True:
        server_output = minecraft_server_process.stdout.readline().strip()

        if not server_output or minecraft_server_process.poll() is not None:
            print('server output read not valid or poll')
            break

        curr_date = datetime.datetime.now().date()

        print(f"MCServerP@{curr_date}: {server_output.strip()}")
        write_output_to_txt(curr_date, server_output)

        if 'Gave' in server_output and 'TNT' in server_output:
            send_command(minecraft_server_process, '/say Use the TNT wisely')

        elif '<' in server_output and '>' in server_output:
            user_name = server_output.split()[3].replace('<', '')
            user_name = user_name.replace('>', '')

            if user_name.upper() in super_users and '!' in server_output:
                handle_user_commands(server_output[server_output.index('!'):])

except KeyboardInterrupt:
    print('Keyboard interrupt, cleaning and exiting')

finally:
    # Close stream and wait for server p to close
    minecraft_server_process.stdin.close()
    minecraft_server_process.wait()
    return_code = minecraft_server_process.returncode
    print(f"Minecraft server process exited with return code: {return_code}")

    # Sets flag and waits for threads to close
    exit_event.set()  # set event flag to close threads
    print('Server process has shut down, enter [Q] to exit')
    input_thread.join()
    backup_thread.join()

exit()