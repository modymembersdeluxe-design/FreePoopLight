#!/usr/bin/env python3
import tkinter as tk
from gui import FreePoopApp

def main():
    root = tk.Tk()
    root.title("FreePoop Light — Super Deluxe (Tkinter Deluxe)")
    app = FreePoopApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()