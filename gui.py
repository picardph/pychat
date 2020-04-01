import tkinter
import tkinter.messagebox
import tkinter.simpledialog
import re
import chat
import emoji

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
    def __init__(self, send_callback, master=None, **kw):
        super().__init__(master, **kw)

        self.__callback = send_callback

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

    def add_message(self, msg):
        self.__msg_list.insert(tkinter.END, replace_emoji(msg))

    def clear_messages(self):
        self.__msg_list.delete(0, tkinter.END)

    def __send(self, arg=None):
        self.add_message('You: ' + replace_emoji(self.__msg_entry.get()))
        self.__callback(self.__msg_entry.get())
        self.__msg_entry.delete(0, tkinter.END)


class ConnectDialog(tkinter.Toplevel):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)

        self.__master = master
        # By default we will assume the operation was canceled.
        self.__canceled = True
        self.__name = ''
        self.__address = ''
        self.__port = ''

        # Style the window like a dialog box.
        self.transient(master)
        self.resizable(False, False)

        body = tkinter.Frame(self)
        body.pack(padx=5, pady=5)

        # Create the body of the dialog where the user will enter
        # the address and port number to connect to.
        tkinter.Label(body, text='My name:').grid(row=0, column=0, padx=5, pady=5)
        self.__name_entry = tkinter.Entry(body)
        self.__name_entry.grid(row=0, column=1, padx=5, pady=5)

        tkinter.Label(body, text='Address:').grid(row=1, column=0, padx=5, pady=5)
        self.__address_entry = tkinter.Entry(body)
        self.__address_entry.grid(row=1, column=1, padx=5, pady=5)

        tkinter.Label(body, text='Port:').grid(row=2, column=0, padx=5, pady=5)
        self.__port_entry = tkinter.Entry(body)
        self.__port_entry.grid(row=2, column=1, padx=5, pady=5)

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
        self.__name_entry.focus_set()
        self.wait_window(self)

    def __ok(self, event=None):
        # Copy over the values that the user entered.
        self.__name = self.__name_entry.get()
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

    def get_username(self):
        return self.__name

    def get_address(self):
        return self.__address

    def get_port(self):
        return int(self.__port)


class ChatTk(tkinter.Tk):
    def __init__(self):
        super().__init__()

        self.tk.call('encoding', 'system', 'utf-8')

        self.title('pychat')
        self.geometry('400x300')

        self.__net = None

        # Create the menu bar that goes across the top.
        menu = tkinter.Menu(self)
        self.config(menu=menu)

        file = tkinter.Menu(menu, tearoff=False)
        file.add_command(label='Connect', command=self.__connect)
        file.add_command(label='Disconnect', command=self.__disconnect)
        file.add_command(label='Host', command=self.__host)
        file.add_separator()
        file.add_command(label='Exit', command=self.__exit)
        menu.add_cascade(label='File', menu=file)

        self.__chat = ChatFrame(self.__send, self)
        self.protocol('WM_DELETE_WINDOW', self.__closing)

    def __exit(self):
        self.__closing()
        self.quit()

    def __thread_error(self, msg):
        tkinter.messagebox.showerror('Error!', msg)

    def __closing(self):
        if self.__net is not None and not self.__net.is_done():
            self.__net.stop()
        self.destroy()

    def __got_message(self, msg):
        self.__chat.add_message(self.__net.get_connected_username() + ': ' + msg)

    def __send(self, msg):
        try:
            if self.__net is None:
                raise RuntimeError('No chat connected.')
            if self.__net.is_done():
                raise RuntimeError('Chat is already finished.')
            self.__net.send_message(msg)
        except RuntimeError as e:
            tkinter.messagebox.showerror('Error!', str(e))

    def __connect(self):
        dialog = ConnectDialog(self)
        if not dialog.was_canceled():
            try:
                if self.__net is not None and not self.__net.is_done():
                    raise RuntimeError('Chat is already running.')
                self.__net = chat.Chat(dialog.get_username(), self.__got_message, self.__thread_error)
                self.__net.connect(dialog.get_address(), dialog.get_port())
            except RuntimeError as e:
                tkinter.messagebox.showerror('Error!', str(e))

    def __disconnect(self):
        self.__chat.clear_messages()
        if self.__net is not None and not self.__net.is_done():
            self.__net.stop()

    def __host(self):
        dialog = ConnectDialog(self)
        if not dialog.was_canceled():
            try:
                if self.__net is not None and not self.__net.is_done():
                    raise RuntimeError('Chat is already running.')
                self.__net = chat.Chat(dialog.get_username(), self.__got_message, self.__thread_error)
                self.__net.host(dialog.get_address(), dialog.get_port())
            except RuntimeError as e:
                tkinter.messagebox.showerror('Error!', str(e))

    def get_username(self):
        return self.__user

    def get_default_port(self):
        return self.__port
