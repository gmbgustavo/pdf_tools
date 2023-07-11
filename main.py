import pikepdf

passwords_filename = "passwords.txt"

locked_pdf_file = "my_locked.pdf"

# load passwords file
with open(passwords_filename) as file:
    passwords_list = file.readlines()
    total_passwords = len(passwords_list)

    for index, password in enumerate(passwords_list):

        # try if password is correct
        try:
            with pikepdf.open(locked_pdf_file, password=password.strip()) as pdf_file:
                print("\n++++++++++++++++++++++SUCCESS+++++++++++++++")
                print("Success---------- File is Unlocked and the password is: ", password)
                break
        # if password fail
        except:
            print("\n=====================")
            print(f"Trying Password {password} --- Fail!!!!")
            scanning = (index / total_passwords) * 100
            print("Scanning passwords complete:", round(scanning, 2))
            continue
