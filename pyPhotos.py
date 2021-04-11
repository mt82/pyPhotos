from gphotospy import authorize
from gphotospy.album import Album
from gphotospy.media import Media,MediaItem
import os
import numpy as np
import pandas as pd
import requests
import json
import time
from cv2 import cv2
from PIL import Image

import email, smtplib, ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

conf = {}

def get_conf():
    for i, row in pd.read_csv("conf",header=None,names=["key","value"]).iterrows():
        conf[row["key"]] = row["value"]

#https://dev.to/davidedelpapa/manage-your-google-photo-account-with-python-p-1-9m2

def create_message(conf, 
                    subject, 
                    body):
    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = conf["sender"]
    message["To"] = conf["receiver"]
    message["Subject"] = subject
    message["Bcc"] = conf["receiver"]  # Recommended for mass emails

    # Add body to email
    message.attach(MIMEText(body, "plain"))
    return message

def get_attachment(filepng,filename):
    # Open PDF file in binary mode
    with open(filepng, "rb") as attachment:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    # Encode file in ASCII characters to send by email    
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename={filename}",
    )

    return part

def send_mail(conf, text):
    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.bo.infn.it", 587) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(conf["user"], conf["password"])
        server.sendmail(conf["sender"], conf["receiver"], text)

def checkImage(filename):
    if not os.path.isfile(filename):
        return False
    else:
        try:
            img = Image.open(filename) # open the image file
            img.verify() # verify that it is, in fact an image
            return True
        except:
            return False

def checkVideo(filename):
    if not os.path.isfile(filename):
        return False
    else:
        try:
            vid = cv2.VideoCapture(filename)
            if not vid.isOpened():
                return False
            else:
                return True
        except:
            return False

CLIENT_SECRET_FILE = "gphoto_oauth.json"

directory = "./Google Photos"

flog = "./log/" + time.strftime("%Y%m%d-%H%M%S") + ".log"

try:
    service = authorize.init(CLIENT_SECRET_FILE)
except:
    message = create_message(conf, 
                        "pyPhotos: Token has been expired or revoked", 
                        "pyPhotos: Token has been expired or revoked\n" \
                        "1- Remove 'photoslibrary_v1.token'\n"\
                        "2- Run 'pyPhotos.py'\n")
    send_mail(conf, message.as_string())
    exit(1)

album_manager = Album(service)
media_manager = Media(service)

album_iterator = album_manager.list()
media_iterator = media_manager.list()

output_dir_root = "./Google Photos/"

f = open(flog,"w")

all_media = {}

try:
    for m in media_iterator:
        if m["id"] not in all_media:
            all_media[m["id"]] = {}
        all_media[m["id"]][m["mediaMetadata"]["creationTime"]] = m["filename"]
        media = MediaItem(m)
        year = m["mediaMetadata"]["creationTime"][:4]
        output_dir = output_dir_root + "Photos from " + year + "/"
        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)
        output_path = output_dir + m["filename"]
        f.write(f"'{output_path}',{os.path.isfile(output_path)}")
        if not os.path.isfile(output_path):
            with open(output_path, 'wb') as output:
                output.write(media.raw_download())
        ftype=m["mimeType"].split('/')[0]
        if ftype == "image":
            status=checkImage(output_path)
            f.write(f",{status}\n")
        elif ftype == "video":
            status=checkVideo(output_path)
            f.write(f",{status}\n")               


        # metadata
        output_json_path = output_path + ".json"
        f.write(f"'{output_json_path}',{os.path.isfile(output_json_path)}")
        if not os.path.isfile(output_json_path):
            with open(output_json_path, 'w') as output:
                json.dump(media.metadata(),output,indent=4)
        f.write(f",{os.path.isfile(output_json_path)}\n")
except:
    pass

for a in album_iterator:
    album_id = a.get("id")
    items = media_manager.search_album(album_id)
    try:
        for m in items:
            media = MediaItem(m)
            output_dir = output_dir_root + a["title"] + "/"
            if not os.path.isdir(output_dir):
                os.mkdir(output_dir)
            if m["id"] not in all_media:
                continue
            if m["mediaMetadata"]["creationTime"] not in all_media[m["id"]]:
                continue
            filename = all_media[m["id"]][m["mediaMetadata"]["creationTime"]]
            output_path = output_dir + filename
            f.write(f"'{output_path}',{os.path.isfile(output_path)}")
            if not os.path.isfile(output_path):
                f.write(f"saving {output_path}\n")
                with open(output_path, 'wb') as output:
                    output.write(media.raw_download())
            ftype=m["mimeType"].split('/')[0]
            if ftype == "image":
                status=checkImage(output_path)
                f.write(f",{status}\n")
            elif ftype == "video":
                status=checkVideo(output_path)
                f.write(f",{status}\n")               

            # metadata
            output_json_path = output_path + ".json"
            f.write(f"'{output_json_path}',{os.path.isfile(output_json_path)}")
            if not os.path.isfile(output_json_path):
                f.write(f"saving {output_json_path}\n")
                with open(output_json_path, 'w') as output:
                    json.dump(media.metadata(),output,indent=4)
            f.write(f",{os.path.isfile(output_json_path)}\n")
    except:
        pass

f.close()

df = pd.read_csv(flog,header=None)
df.columns = ["file","presence_before","integrity"]

for index, row in df[df["integrity"] == False].iterrows():
    os.remove(row['file'])