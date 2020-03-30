import tkinter
import tkinter.messagebox
import tkinter.simpledialog
import json
import appdirs
import os
import re

# This is a hack to get emojis to work with tkinter because
# tkinter has a bug (I confirmed this with a developer from
# the tkinter project) in that it can't render unicode characters
# in the emoji range. It can use the surrogate pairs however and
# this function will replace all the emojis with the surrogate pair
# to get it to work. This problem was solved with help from
# https://stackoverflow.com/questions/40222971/python-find-equivalent-surrogate-pair-from-non-bmp-unicode-char
replace_regex = re.compile(r'[\U00010000-\U0010FFFF]')


def match_surrogate(match):
    c = match.group()
    encoded = c.encode('utf-16-le')
    return chr(int.from_bytes(encoded[:2], 'little')) + chr(int.from_bytes(encoded[2:], 'little'))


def replace_emoji(string):
    return replace_regex.sub(match_surrogate, string)


class ChatFrame(tkinter.Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)

        # Allow the frame widget to take up the entire window.
        self.pack(fill=tkinter.BOTH, expand=True)

        # This sub-frame is used to make the chat box span the length of the window.
        bottom_frame = tkinter.Frame(self).pack(side=tkinter.BOTTOM)

        self.__msg_entry = tkinter.Entry(bottom_frame)
        self.__msg_entry.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True, padx=5, pady=5)
        self.__msg_entry.bind('<Return>', self.__send)

        send_btn = tkinter.Button(bottom_frame, text=replace_emoji('➡'), command=self.__send)
        send_btn.pack(side=tkinter.RIGHT, padx=5, pady=5)

        scroll = tkinter.Scrollbar(self, orient=tkinter.VERTICAL)

        self.__msg_list = tkinter.Listbox(self, yscrollcommand=scroll.set)
        self.__msg_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=5, pady=5)

        scroll.config(command=self.__msg_list.yview)
        scroll.pack(side=tkinter.RIGHT, fill=tkinter.Y)

    def __send(self):
        pass


class ConnectDialog(tkinter.Toplevel):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)

        self.__master = master
        # By default we will assume the operation was canceled.
        self.__canceled = True
        self.__address = ''
        self.__port = ''

        # Style the window like a dialog box.
        self.transient(master)
        self.resizable(False, False)

        body = tkinter.Frame(self)
        body.pack(padx=5, pady=5)

        # Create the body of the dialog where the user will enter
        # the address and port number to connect to.
        tkinter.Label(body, text='Address:').grid(row=0, column=0, padx=5, pady=5)
        self.__address_entry = tkinter.Entry(body)
        self.__address_entry.grid(row=0, column=1, padx=5, pady=5)

        tkinter.Label(body, text='Port:').grid(row=1, column=0, padx=5, pady=5)
        self.__port_entry = tkinter.Entry(body)
        self.__port_entry.grid(row=1, column=1, padx=5, pady=5)

        # Create the buttons on the bottom.
        buttons = tkinter.Frame(self)
        ok_btn = tkinter.Button(buttons, text='OK', width=10, default=tkinter.ACTIVE, command=self.__ok)
        ok_btn.pack(side=tkinter.RIGHT, padx=5, pady=5)
        cancel_btn = tkinter.Button(buttons, text='Cancel', width=10, command=self.__cancel)
        cancel_btn.pack(side=tkinter.RIGHT, padx=5, pady=5)
        buttons.pack()

        tkinter.Label(body, text='Port:')

        self.bind('<Return>', self.__ok)
        self.bind('<Escape>', self.__cancel)

        self.geometry("+%d+%d" % (master.winfo_rootx() + 50, master.winfo_rooty() + 50))

        # Give ourselves focus since we are a popup dialog.
        self.grab_set()
        self.__address_entry.focus_set()
        self.wait_window(self)

    def __ok(self, event=None):
        # Copy over the values that the user entered.
        self.__address = self.__address_entry.get()
        self.__port = self.__port_entry.get()

        self.__canceled = False
        self.__master.focus_set()
        self.destroy()

    def __cancel(self):
        self.__master.focus_set()
        self.destroy()

    def was_canceled(self):
        return self.__canceled

    def get_address(self):
        return self.__address

    def get_port(self):
        return self.__port


class SettingsDialog(tkinter.Toplevel):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)

        self.__master = master

        # Style the window like a dialog box.
        self.transient(master)
        self.resizable(False, False)

        body = tkinter.Frame(self)
        body.pack(padx=5, pady=5)

        # Create the body of the dialog where the user will enter
        # the new settings.
        tkinter.Label(body, text='Username:').grid(row=0, column=0, padx=5, pady=5)
        self.__name_entry = tkinter.Entry(body)
        self.__name_entry.grid(row=0, column=1, padx=5, pady=5)

        tkinter.Label(body, text='Port:').grid(row=1, column=0, padx=5, pady=5)
        self.__port_spin = tkinter.Spinbox(body, from_=0, to=65535)
        self.__port_spin.grid(row=1, column=1, padx=5, pady=5)

        # Create the buttons on the bottom.
        buttons = tkinter.Frame(self)
        ok_btn = tkinter.Button(buttons, text='OK', width=10, default=tkinter.ACTIVE, command=self.__ok)
        ok_btn.pack(side=tkinter.RIGHT, padx=5, pady=5)
        cancel_btn = tkinter.Button(buttons, text='Cancel', width=10, command=self.__cancel)
        cancel_btn.pack(side=tkinter.RIGHT, padx=5, pady=5)
        buttons.pack()

        tkinter.Label(body, text='Port:')

        self.bind('<Return>', self.__ok)
        self.bind('<Escape>', self.__cancel)

        self.geometry("+%d+%d" % (master.winfo_rootx() + 50, master.winfo_rooty() + 50))

        # Fill out the dialog with the current settings.
        self.__name_entry.delete(0, tkinter.END)
        self.__port_spin.delete(0, tkinter.END)
        self.__name_entry.insert(0, master.get_username())
        self.__port_spin.insert(0, master.get_default_port())

        # Give ourselves focus since we are a popup dialog. Unlike the connection dialog
        # we will not give focus to the text box right away since by default a user does
        # not change the settings.
        self.grab_set()
        self.wait_window(self)

    def __ok(self, event=None):
        self.master.save_settings(self.__name_entry.get(), self.__port_spin.get())
        self.__master.focus_set()
        self.destroy()

    def __cancel(self):
        self.__master.focus_set()
        self.destroy()


class ChatTk(tkinter.Tk):
    def __init__(self):
        super().__init__()
        self.title('pychat')
        self.geometry('400x300')

        # Load the current settings from the JSON file if there are already
        # settings. If there is no settings file then we will create one with
        # default values.
        self.__path = appdirs.user_config_dir('pychat')
        self.__user = '[name not set]'
        self.__port = '5138'
        # We may need to make the path if it does not already exist.
        if not os.path.isdir(self.__path):
            os.makedirs(self.__path)
        self.__path += '/settings.json'
        if os.path.isfile(self.__path):
            try:
                f = open(self.__path, 'r')
                data = json.loads(f.read())
                f.close()

                self.__user = data['user']
                self.__port = data['port']
            # If there is a problem while trying to load the settings, we will inform the user and just
            # use the default settings.
            except json.JSONDecodeError:
                tkinter.messagebox.showerror('JSON Error', 'Unable to decode the JSON settings file.')
            except (OSError, IOError):
                tkinter.messagebox.showerror('File Error', 'Unable to open the settings file for reading.')
        # There is no settings file yet so we will create one with the default settings.
        else:
            self.save_settings(self.__user, self.__port)

        # Create the menu bar that goes across the top.
        menu = tkinter.Menu(self)
        self.config(menu=menu)

        file = tkinter.Menu(menu, tearoff=False)
        file.add_command(label='Connect', command=self.__connect)
        file.add_command(label='Disconnect', command=self.__disconnect)
        file.add_command(label='Host', command=self.__settings)
        file.add_separator()
        file.add_command(label='Exit', command=self.quit)
        menu.add_cascade(label='File', menu=file)

        self.__chat = ChatFrame(self)

    def __connect(self):
        dialog = ConnectDialog(self)
        if not dialog.was_canceled():
            pass

    def __disconnect(self):
        pass

    def __settings(self):
        SettingsDialog(self)

    def save_settings(self, user, port):
        self.__user = user
        self.__port = port
        try:
            f = open(self.__path, 'w')
            data = {
                'user': self.__user,
                'port': self.__port
            }
            f.write(json.dumps(data))
            f.close()
        except (OSError, IOError):
            tkinter.messagebox.showerror('File Error', 'Unable to write the requested settings.')

    def get_username(self):
        return self.__user

    def get_default_port(self):
        return self.__port
