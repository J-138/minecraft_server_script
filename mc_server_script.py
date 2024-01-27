import subprocess
import threading
import datetime
import shutil
import time
import os

# Start the Minecraft server as a subprocess
server_jar = 'server.jar'
minecraft_server_process = subprocess.Popen(['java', 
                                             '-jar', 
                                             server_jar,
                                             'nogui'],
                                             stdin=subprocess.PIPE, 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE, 
                                             universal_newlines=True)

# Sends input to mc server process
def send_command(p, user_command: str) -> None:
    p.stdin.write(user_command + '\n')
    p.stdin.flush()

# Function for user input thread
def user_input_thread():
    while True:
        user_input = input()

        if user_input.upper() == 'Q' or exit_event.is_set():
            break

        send_command(minecraft_server_process, user_input)

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

# Variables for backing up world
exit_event = threading.Event()
TIME_BETWEEN_BACKUPS = 1200 # How often backups are make, in seconds

# Create backup world
def backup_world():
    curr_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir_name = 'world_' + curr_time
    dst_dir = os.path.join('./world_backups', backup_dir_name)

    if not os.path.exists('./world_backups'):
        os.makedirs('./world_backups')
        print('Created \'./world_backups\' directory')
    
    try:
        shutil.copytree('./world',
                        dst_dir,
                        ignore=shutil.ignore_patterns('*.lock'))
        
        print(f"Backup completed")
        world_size = find_dir_size(dst_dir)
        bu_msg = f'World backed up on: {curr_time}, current world size: {world_size}'
        send_command(minecraft_server_process, f'/say {bu_msg}')
    
    except Exception as e:
        print(f"Backup failed. An error occurred: {e}")
        send_command(minecraft_server_process, '/say World backup failed')

# Function for backup thread
def check_backup_thread():
    last_backup_time = time.time()

    while True:
        if (time.time() - last_backup_time) >= TIME_BETWEEN_BACKUPS:
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
while True:
    server_output = minecraft_server_process.stdout.readline()

    if not server_output and minecraft_server_process.poll() is not None:
        break

    curr_date = datetime.datetime.now().date()

    print(f"MCServerP@{curr_date}: {server_output.strip()}")
    write_output_to_txt(curr_date, server_output)

    if 'Gave' in server_output and 'TNT' in server_output:
        send_command(minecraft_server_process, '/say Use the TNT wisely')

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