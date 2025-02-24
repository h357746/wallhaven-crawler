import base64

open_icon = open("background.png", "rb")
b64str = base64.b64encode(open_icon.read())
open_icon.close()
write_data = "backgroundImg = %s" % b64str
f = open("background.py", "w+")
f.write(write_data)
f.close()
