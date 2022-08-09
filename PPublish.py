#!/usr/bin/env python3
import os
import subprocess
import time
import datetime
import copy
from datetime import datetime
import hashlib
import pickle
import re
import audioread

current_states = {}
new_state = {}
save = {}


def getNameStart(string):
	match = re.search('[a-zA-Z0-9][^). ]+', string)
	if match==None:
		return 0
	return match.start()

class File:
	def __init__(self, path):
		self.path=path
		self.valid=os.path.isfile(path)
		if self.valid:
			self.md5=self.hash()

	def hash(self):
		with open(self.path, "rb") as f:
			file_hash = hashlib.md5()
			while chunk := f.read(8192):
				file_hash.update(chunk)

			return file_hash.hexdigest()

	def __eq__(self, Other):
		if type(Other)==type(self):
			return self.md5==Other.md5
		return False


class Track(File):
	def __init__(self, file, index):
		super().__init__(file)
		self.index=index
		self.load()

	def load(self):
		if self.valid:
			self.length = self.getlength()
		self.name=self.load_name()

	def move(self, path):
		self.path=path
		self.load()

	def load_name(self):
		file = self.path.split("/")[-1]

		# get Name begining
		start=getNameStart(file)
		if start==None:
			return "Unknown"
		end=file.rfind(".")

		# get name end
		return file[start:end]

	def getlength(self):
		return audioread.audio_open(self.path).duration
	def __eq__(self, Other):
		if type(Other)==type(self):
			return self.md5==Other.md5
		return False
	def __str__(self):
		return self.name

#updates
class RenameTrack:
	def __init__(self, md5, new_path):
		self.md5=md5
		self.new_path = new_path

	def apply(self, state):
		track = getTrackByMD5(state["Tracks"], self.md5)
		if track == None:
			print("[ERROR] Could not find Track in state hash: "+self.md5)
			return True
		track.move(self.new_path)
		return False

class RenameAlbum:
	def __init__(self, new_name):
		self.new_name=new_name
	def apply(self, state):
		state["Album"]=self.new_name
		return False

class ChangePath:
	def __init__(self, module, path):
		self.module=module
		self.path=path
	def apply(self, state):
		state[self.module+"_path"]=self.path
		return False

class UpdateTrack:
	def __init__(self, Track):
		self.track = Track
	def apply(self, state):
		return False

class NewTrack:
	def __init__(self, Track):
		self.track = Track
	def apply(self, state):
		state["Tracks"].append(copy.deepcopy(self.track))
		return False

class DeleteTrack:
	def __init__(self, Track):
		self.track = Track
	def apply(self, state):
		state["Tracks"].remove(self.track)
		return False
#
#class UpateCover:
#	def __init__(self, path):
#		self.path=path

class UpdateVideo:
	def __init__(self, path):
		self.path=path
	def apply(self, state):
		state["Video"]=self.path
		return False

class Updatemp3tags:
	def __init__(self, tags):
		self.tags = tags
	def apply(self, state):
		state["tags"]=copy.copy(self.tags)
		return False

class Reorder:
	def __init__(self, md5, index):
		self.md5=md5
		self.index = index
	def apply(self, state):
		track = getTrackByMD5(state["Tracks"], self.md5)
		if track == None:
			print("[ERROR] Could not find Track in state hash: "+self.md5)
			return True
		track.index = self.index
		return False

class Initilize:
	def __init__(self, path, module):
		self.path=path
		self.module=module
	def apply(self, state):
		state[self.module+"_path"]=self.path
		return False

class Start:
	def __init__(self):
		pass

class End:
	def __init__(self):
		pass

class Clear:
	def __init__(self):
		pass
	def apply(self, state):
		pass



def getTrackByMD5(Tracks, md5):
	same = [t for t in Tracks if t.md5==md5]
	if len(same)==0:
		return None
	if len(same)>1:
		print("[WARNING] Duplicate Tracks found!")
		print(same)
	return same[0]

def getTrackByName(Tracks, name):
	same = [t for t in Tracks if t.name==name]
	if len(same)==0:
		return None
	if len(same)>1:
		print("[WARNING] Duplicate Tracks found!")
		print(same)
	return same[0]


audio_fmt = ["mp3", "wav", "wma", "flac"]
image_fmt = ["png", "bmp", "jpg", "tiff"]
video_fmt = ["avi", "mp4", "flv", "mkv"]

fmts = audio_fmt+image_fmt+video_fmt


def track_add(state, path):

	path.replace("\\", "/")
	if not path.count("/"):
		path = "./"+path

	if not path.split(".")[-1] in audio_fmt:
		print(path +" is not an audio file!")
		return path + " is not a audio file!"

	if path in state["removed"]:
		state["removed"].remove(path)

	track = Track(path, len(state["Tracks"])+1)
	if not track.valid:
		print("File does not exist")
		return "File is invalid"

	dup = getTrackByMD5(state["Tracks"], track.md5)
	twin = getTrackByName(state["Tracks"], track.name)
	if dup:
		if dup.path!=track.path:
			print("sub" + dup.path + " ->" + track.path)
			dup.move(path)
	elif twin:
		print("sub " + twin.path + " hash!")
		twin.md5=track.md5
	else:
		print("Loading Track "+track.path)
		state["Tracks"].append(track)

def track_rm(state, track):
	index= track.index
	print("Removed "+track.name)
	state["removed"].append(track.path)
	state["Tracks"].remove(track)
	for track in state["Tracks"]:
		if track.index>index:
			track.index-=1

def track_rmn(state, name):
	track = getTrackByName(state["Tracks"], name)
	if track == None:
		print("[ERROR] Could not find Track \""+name+"\"")
		return "Track not found"
	track_rm(state, track)

def track_rmi(state, index):
	num = int(index)
	tracks = [i for i in state["Tracks"] if i.index==num]
	for track in tracks:
		track_rm(state, track)

def Tracks_sort(Tracks):
	Tracks.sort(key=lambda x: x.index)

def dir_prep(directory):
	directory=directory.strip()
	if len(directory)==0:
		directory="."

	directory.replace("\\","/")
	if directory[-1]!="/":
		directory+="/"
	return directory

def dir_add(state, save, directory):

	directory = dir_prep(directory)
	if not directory in state["dirs"] and save:
		state["dirs"].append(directory)

	# Get all songs in directory
	for f in os.listdir(directory):
		path = directory+f
		if os.path.isfile(path) and f.split(".")[-1] in audio_fmt and not path in state["removed"]:
			track_add(state, path)

def dir_rm(state, directory):

	directory = dir_prep(directory)
	if directory in state["dirs"]:
		state["dirs"].remove(directory)

	# Get all songs in directory
	for track in reversed(state["Tracks"]):
		if track.path.startswith(directory):
			track_rm(state, track)



def dir_relevant(path):
	files = []
	for file in os.listdir(path):
		if file.split(".")[-1] in fmts:
			files.append(file)
	return files

def getName():
	folder = os.getcwd().replace("\\","/").split("/")[-1]
	start = getNameStart(folder)
	return folder[start:]

def getCover():
	tmp = [f for f in os.listdir() if len(f.split("."))==2]
	for file in tmp:
		l = file.lower().split(".")
		if l[0]=="cover" and l[1] in image_fmt:
			return File(file)

def getVideo():
	tmp = [f for f in os.listdir() if len(f.split("."))==2]
	for file in tmp:
		l = file.lower().split(".")
		if l[0].startswith("vid") and l[1] in video_fmt:
			return File(file)
	return getCover()

default_paths = { "mp3_path" : "",
				  "wav_path" : " HQ",
				  "video_path" : ".mp4",
				  "full_path" : "mp3"
				  }

def setName(conf, name):
	paths = [i for i in conf if i.endswith("_path")]
	for i in paths:
		if not len(conf[i]):
			if i in default_paths:
				suffix=default_paths[i]
			else:
				suffix=" "+i[:i.index("_path")-1]
			conf[i] = name + suffix

		elif conf[i].startswith(conf["Album"]):
			conf[i] = conf[i].replace(conf["Album"], name)

	conf["Album"] = name

def conf_detect(conf):
	dir_add(conf, True, "./")
	#album name
	setName(conf, getName())
	conf["tags"]["Cover"]  = getCover()
	conf["Video"] = getVideo()

def Rename(old_name, new_name):
	changed=False
	while not changed:
		try:
			os.rename(old_name, new_name)
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.Sleep(1)
			continue
		except Exception as e:
			print("Could not rename : "+str(e))
			return True
	return False

def Delete(file):
	changed=False
	while not changed:
		try:
			os.remove(file)
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.Sleep(1)
			continue
		except FileNotFoundError:
			break
		except Exception as e:
			print("Could not remove : "+str(e))
			return True
	return False

def dir_Delete(file):
	changed=False
	while not changed:
		try:
			os.rmdir(file)
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.Sleep(1)
			continue
		except FileNotFoundError:
			break
		except Exception as e:
			print("Could not remove : "+str(e))
			return True
	return False

def Reset(module):
	module.clear()
	module.path=""
	#module.state_set(current_states[module.name])


class module:
	def __init__(self):
		self.name = type(self).__name__

	def state_set(self, state):
		self.state = state
		self.load()

	def load(self):
		self.Tracks = self.state["Tracks"]
		self.Album = self.state["Album"]
	def start(self):
		pass
	def end(self):
		pass
	def verify(self, new_state):
		pass
	def handle(self, task, update):
		pass
	def __str__(self):
		return self.name

	def description(self):
		return ""

class mp3(module):
	def __init__(self):
		super().__init__()

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Cover = self.state["tags"]["Cover"]
		self.tags = self.state["tags"]

	def retag_track(self, track):
		if not track in self.retag and not track in self.rerender:
			self.retag.append(track)

	def rerender_track(self, track):
		if track in self.retag:
			self.retag.remove(track)
		if not track in self.rerender:
			self.rerender.append(track)

	def start(self):
		self.retag = []
		self.rerender = []

	def end(self):
		for track in self.rerender:
			self.Render(track)

		for track in self.retag:
			self.ReTag(track)

	def verify(self, new_state):
		if not os.path.exists(self.path):
			Reset(self)
		else:
			for track in reversed(self.Tracks):
				if not self.getName(track.index, track.name) in os.listdir(self.path):
					self.Tracks.remove(track)

	def description(self):
		return "Creates tagged mp3 files of file with integraded Album Cover"

	def handle(self, task, update):
		if task == "RenameTrack":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find Track in state hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+track.path+"\"")
				return True

			new_name = self.getName(track.index, update.new_name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))
			self.retag_track(track)

		elif task == "ChangePath":
			if update.module==self.name:
				return Rename(self.path, update.path)

		elif task == "NewTrack":
			self.rerender_track(update.track)

		elif task == "UpdateTrack":
			track = getTrackByName(self.Tracks, update.track.name)
			if track == None:
				print("[ERROR] Could not find Track \""+update.track.name+"\"")
				return True
			self.rerender_track(track)
			track.md5=update.track.md5

		elif task == "DeleteTrack":
			self.delete(update.track)

		elif task == "Updatemp3tags":
			for track in self.Tracks:
				self.retag_track(track)

		elif task == "Reorder":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find track! hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			new_name = self.getName(update.index,track.name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))

			self.retag_track(track)

		elif task == "Initilize":
			try:
				os.mkdir(update.path)
			except:
				pass

		elif task == "Clear":
			clear()



		return False

	def getName(self, index, name):
		return str(index)+". "+name+".mp3"

	def ReTag(self, track):
		name=self.getName(track.index,track.name)
		if not name in os.listdir(self.path):
			print("[ERROR] could not find Track \""+track.name+"\"")
			return True
		if Rename(os.path.join(self.path, name), os.path.join(self.path, "tmp_"+name)):
			return True

		os.system("ffmpeg -i \"{}\" -i \"{}\" -map 0:0 -map 1:0 -c:a copy -id3v2_version 3 -metadata title=\"{}\" -metadata track=\"{}\" -metadata album_artist=\"{}\" -metadata album=\"{}\" -metadata genre=\"{}\" -metadata artist=\"{}\" \"{}\" -y".format(
				os.path.join(self.path,"tmp_"+name),
				self.Cover.path,
				track.name,
				track.index,
				self.tags["Artist"],
				self.Album,
				self.tags["Genre"],
				", ".join(self.tags["feat"]),
				os.path.join(self.path,
				self.getName(track.index, track.name)))
			)
		Delete(os.path.join(self.path, "tmp_"+name))

	def Render(self, track):
		os.system("ffmpeg -i \"{}\" -i \"{}\" -map 0:0 -map 1:0 -b:a 320k -acodec libmp3lame -id3v2_version 3 -metadata title=\"{}\" -metadata track=\"{}\" -metadata album_artist=\"{}\" -metadata album=\"{}\" -metadata genre=\"{}\" -metadata artist=\"{}\" \"{}\" -y".format(
				track.path,
				self.Cover.path,
				track.name,
				track.index,
				self.tags["Artist"],
				self.Album,
				self.tags["Genre"],
				", ".join(self.tags["feat"]),
				os.path.join(self.path,
				self.getName(track.index, track.name)))
			)

	def delete(self, Track):
		Delete(os.path.join(self.path,self.getName(Track.index,Track.name)))

	def clear(self):
		for track in self.Tracks:
			self.delete(track)
		self.Tracks.clear()
		dir_Delete(self.path)
		self.path=""


class wav(module):
	def __init__(self):
		super().__init__()

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Cover = self.state["tags"]["Cover"]
		self.tags = self.state["tags"]

	def verify(self, new_state):
		if not os.path.exists(self.path):
			Reset(self)
		else:
			for track in reversed(self.Tracks):
				if not self.getName(track.index, track.name) in os.listdir(self.path):
					self.Tracks.remove(track)

	def description(self):
		return "Creates high quality Wav output of album"

	def handle(self, task, update):
		if task == "RenameTrack":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find Track in state hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			new_name = self.getName(track.index, update.new_name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))
			track.name=update.new_name

		elif task == "ChangePath":
			if update.module==self.name:
				return Rename(self.path, update.path)

		elif task == "NewTrack":
			self.Render(update.track)

		elif task == "UpdateTrack":
			track = getTrackByName(self.Tracks, update.track.name)
			if track == None:
				print("[ERROR] Could not find Track \""+update.track.name+"\"")
				return True
			self.Render(track)
			track.md5=update.track.md5

		elif task == "DeleteTrack":
			self.delete(update.track)

		elif task == "Reorder":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find track! hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			track.index=update.index
			new_name = self.getName(track.index,track.name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))

		elif task == "Initilize":
			try:
				os.mkdir(update.path)
			except:
				pass

		elif task == "Clear":
			clear()


		return False

	def getName(self, index, name):
		return str(index)+". "+name+".wav"

	def Render(self, track):
		os.system("ffmpeg -i \"{}\" -ar 44100 -ac 2 \"{}\" -y".format(
				track.path,
				os.path.join(self.path,
				self.getName(track.index, track.name)))
			)

	def delete(self, Track):
		Delete(os.path.join(self.path,self.getName(Track.index,Track.name)))

	def clear(self):
		for track in self.Tracks:
			self.delete(track)
		self.Tracks.clear()
		dir_Delete(self.path)

class modlue_hash(module):

	def save(self):
		self.state["output"]=File(self.path)
		print("New Hash: " + self.state["output"].md5)

	def search_sub(self, new_state):
		check = self.state["output"]
		found = False
		for file in os.listdir():
			if not os.path.isfile(file):
				continue
			print("candidate " + file)
			file=File(file)
			if file==check:
				print("New path " + file.path)
				self.state[module.name+"_path"]=file.path
				found=True
				break
		if not found:
			print("Noghing Found")
			Reset(self)

	def verify(self, new_state):
		if not "output" in self.state:
			return
		check = self.state["output"]
		if not check.valid:
			print("Wasnt Valid")
			Reset(self)
			return
		print("hash: " + check.md5)
		current = File(self.path)
		if not current.valid:
			print("file moved")
			self.search_sub(new_state)
		elif current!=check:
			print("hash: " + current.md5)
			print("file edit")
			self.search_sub(new_state)
		return

class video(modlue_hash):
	def __init__(self):
		super().__init__()
		self.jobs = [self.Render_video, self.Render_audio, self.Render]

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Video = self.state["Video"]

	def start(self):
		self.job = 0

	def end(self):
		if self.job:
			res = self.jobs[self.job-1]()
			self.save()

			return res
		return False

	def description(self):
		return "Creates an Album video for Youtube, uses either the Cover as a still or a video if found"

	def handle(self, task, update):

		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)

		elif task == "NewTrack":
			self.job=3

		elif task == "UpdateTrack":
			self.job=3

		elif task == "DeleteTrack" or task == "Reorder":
			if self.job==0 or self.job==2:
				self.job=2
			else:
				self.job=3

		elif task == "UpdateVideo":
			if self.job==0 or self.job==1:
				self.job=1
			else:
				self.job=3

		elif task == "Clear":
			clear()

		return False

	def Render(self):
		if not len(self.Tracks):
			return
		self.Tracks.sort(key=lambda x: x.index)
		audio = [ i.path for i in self.Tracks]
		vid_fmt = self.Video.path.split(".")[-1]
		render = "-stream_loop -1"
		if vid_fmt in image_fmt:
			render = "-loop 1"

		video_render = "{} -i {} -map {}:v".format(render, self.Video.path, len(audio))

		os.system("ffmpeg -i \"{}\" {} -filter_complex \"[{}:0]concat=n={}:v=0:a=1[out]\" -map [out] -b:a 320k -tune stillimage -acodec libmp3lame -c:v libx264 -pix_fmt yuv420p -shortest \"{}\" -y".format( "\" -i \"".join(audio), video_render, ":0][".join([str(i) for i in range(len(audio))]), len(audio), self.path)
			)
	def Render_audio(self):
		if not len(self.Tracks):
			return
		Tracks_sort(self.Tracks)
		audio = [ i.path for i in self.Tracks]
		if Rename(self.path, "tmp_"+self.path):
			return True
		os.system("ffmpeg -i \"{}\" -i \"{}\" -filter_complex \"[{}:0]concat=n={}:v=0:a=1[out]\" -map [out] -map {}:v -c:v copy -b:a 320k -acodec libmp3lame -pix_fmt yuv420p -shortest \"{}\" -y".format(
			"\" -i \"".join(audio), "tmp_"+self.path, ":0][".join([str(i) for i in range(len(audio))]), len(audio),len(audio), self.path)
			)
		Delete("tmp_"+self.path)

	def Render_video(self):
		if not len(self.Tracks):
			return
		vid_fmt = self.Video.path.split(".")[-1]
		render = "-stream_loop -1"
		if vid_fmt in image_fmt:
			render = "-loop 1"

		video_render = "{} -i {}".format(render, self.Video.path, len(audio))

		if Rename(self.path, "tmp_"+self.path):
			return True
		os.system("ffmpeg -i \"{}\" {} -map 0:a -map 1:v -b:a 320k -c:a copy -pix_fmt yuv420p -shortest \"{}\" -y".format(
			"tmp_"+self.path, video_render, self.path)
			)
		Delete("tmp_"+self.path)

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)
		Delete("tmp_"+self.path)

class description(module):
	def __init__(self):
		super().__init__()

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Artist = self.state["tags"]["Artist"]
		self.Album = self.state["Album"]

	def start(self):
		self.rerender=False

	def end(self):
		if self.rerender:
			print("Rerendering!")
			self.output()

	def verify(self, new_state):
		pass

	def description(self):
		return "Creates a description for Youtube with timestamps for the Tracks"

	def handle(self, task, update):
		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)
		elif task == "NewTrack" or task == "UpdateTrack" or task == "DeleteTrack" or task == "Reorder":
			self.rerender=True


	def output(self):
		print(self.path)
		i=0
		timestamps = [datetime.fromtimestamp(i:=i+track.length).strftime("%M:%S")+" "+track.name for track in self.Tracks]
		string = "\n".join(timestamps)
		file = open(self.path, "w")
		file.write(self.Artist+"s new Album " + self.Album + " is now on Youtube!!\nEnjoy our latest Tracks UwU\n\nTimestamps:\n")
		file.write(string)
		file.close()

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)

class full(modlue_hash):
	def __init__(self):
		super().__init__()

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Video = self.state["Video"]


	def start(self):
		pass

	def end(self):
		if self.job:
			self.save()
			return res
		return False

	def description(self):
		return "Combines all Tracks into one high quality wav file"

	def handle(self, task, update):
		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)
		elif task == "NewTrack" or task == "UpdateTrack" or task == "DeleteTrack" or task == "Reorder":
			self.rerender=True

		return False

	def render(self):
		audio = f"|{self.Album}/".join([i.path for i in self.Tracks])
		os.system("ffmpeg -i \"concat:{}/{}\" -c copy \"{}\" -y".format(self.Album, audio, self.path))

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)
		self.state[self.name+"_path"]=""

modules = [ mp3(), wav(), video(), description() ]

def conf_default():
	conf = {}

	conf["Tracks"] = []
	conf["Album"] = ""
	conf["dirs"] = []
	conf["removed"] = []

	#mp3 tags
	conf["tags"]={}
	conf["tags"]["Artist"] = "PATRIS PREDICTUM"
	conf["tags"]["Genre"]  = "dominationdead"
	conf["tags"]["feat"]   = []
	conf["tags"]["Cover"]  = None
	conf["Video"] = None

	# module conf
	for module in modules:
		conf[module.name+"_path"] = ""

	conf["description_path"] = "Description.txt"

	return conf

def getDiff(old_state, new_state):
	diff = []
	if old_state["tags"]!=new_state["tags"]:
		diff.append(Updatemp3tags(new_state["tags"]))

	if old_state["Album"]!=new_state["Album"]:
		diff.append(RenameAlbum(new_state["Album"]))
		diff.append(Updatemp3tags(new_state["tags"]))

	for module in modules:
		if module.name+"_path" in old_state:
			if new_state[module.name+"_path"]!=old_state[module.name+"_path"]:
				diff.append(ChangePath(module.name, new_state[module.name+"_path"]))

	if old_state["Video"]!=new_state["Video"]:
		diff.append(UpdateVideo(new_state["Video"]))

	for track in old_state["Tracks"]:
		if track not in new_state["Tracks"]:
			Found=False
			for new_track in new_state["Tracks"]:
				if track.name==new_track.name:
					Found=True
					break
			if not Found:
				diff.append(DeleteTrack(track))
		else:
			for new_track in new_state["Tracks"]:
				if (track == new_state or track.name==new_track.name) and track.index!=new_track.index:
					diff.append(Reorder(track.md5, new_track.index))
				if track==new_track and track.name!=new_track.name:
					diff.append(RenameTrack(track.md5, new_track.name))


	for track in new_state["Tracks"]:
		if not track in old_state["Tracks"]:
			Found=False
			for old_track in old_state["Tracks"]:
				if track.name==old_track.name:
					diff.append(UpdateTrack(old_track))
					Found=True
					break
			if not Found:
				diff.append(NewTrack(track))
	return diff

def module_run(current_state, new_state, module):
	# if no path set initilize
	if not len(module.path):
		module.load()
		init = Initilize(new_state[module.name+"_path"], module.name)
		task = type(init).__name__
		module.handle(task, init)
		init.apply(current_state)
	module.verify(new_state) # veriy Environment before execution
	module.start() # signal start of transactions
	diffs = getDiff(current_state, new_state)
	# pass each change to module handler
	for diff in diffs:
		task = type(diff).__name__
		print(module.name + " -> " + task)
		module.load()
		if module.handle(task, diff):
			break
		diff.apply(current_state) # apply difference
	module.end()


savefile = ".ppub"
def pub_save():
	save["current_states"]=current_states
	save["new_state"]=new_state
	pickle.dump(save, open(savefile, "wb"))

if savefile in os.listdir():
	save = pickle.load(open(savefile, "rb"))

	current_states = save["current_states"]
	new_state = save["new_state"]


	for module in modules:
		if not module.name in current_states:
			current_states[module.name] = conf_default()
			new_state[module.name+"_path"]=""
		module.state_set(current_states[module.name])

	for directory in new_state["dirs"]:
		dir_add(new_state, False, directory)
else:
	print("---Analyzing Environment---")
	new_state = conf_default()

	conf_detect(new_state)
	for module in modules:
		current_states[module.name] = conf_default()

	for module in modules:
		module.state_set(current_states[module.name])

	pub_save()
	print("--------------")

def Tracks_length(Tracks):
	return datetime.fromtimestamp(sum([i.length for i in Tracks])).strftime("%M:%S")

print("Album name: " + new_state["Album"])
print("Found {} Songs".format(len(new_state["Tracks"])))
print("Cover: " + new_state["tags"]["Cover"].path)
print("Video: " + new_state["Video"].path)
print("Album length: " + Tracks_length(new_state["Tracks"]))
#print("Tags: " + str(new_state["tags"]))

# set simple fiels
var_set = { "Cover"   : [new_state["tags"]],
		     "Video"  : [new_state],
		     "Artist" : [new_state["tags"]],
		     "Genre"  : [new_state["tags"]],
		     "Album"  :	[new_state,  setName]
		   }
#append paths to var_set
for module in modules:
	var_set[module.name+"_path"]=[new_state]

class cmd:
	def run(self, args):
		pass

	def description(self):
		return "Not Documented"

	def usage(self):
		return "No Usage"

class cmd_unary(cmd):
	def usage(self):
		return self.id()
	def _run(self):
		pass

	def run(self, args):
		if not len(args):
			return self._run()
		else:
			return self.id() + " takes no args"

class cmd_save(cmd_unary):
	def _run(self):
		pub_save()
		pass

	def description(self):
		return "Saves current states to .ppub"

	def id(self):
		return "save"
class cmd_detect(cmd_unary):
	def _run(self):
		conf_detect(new_state)
		for directory in new_state["dirs"]:
			dir_add(new_state, False, directory)

	def description(self):
		return "Detects Environment eg.\ncheck monitored directories for Tracks,\nGuess Album from Folder name\nSearch Cover and Video files"

	def id(self):
		return "detect"

class cmd_check(cmd_unary):
	def _run(self):
		for directory in new_state["dirs"]:
			dir_add(new_state, False, directory)

	def description(self):
		return "Checks all monitored directories for new Tracks"

	def id(self):
		return "check"

class cmd_set_vars(cmd):
	def __init__(self, var_set):
		self.var_set = var_set

	def run(self, args):
		if len(args)>1:
			found = False
			for var in self.var_set:
				if var.lower()==args[0].lower():
					found = True
					arg = " ".join(args[1:])
					if len(self.var_set[var])==2:
						self.var_set[var][1](self.var_set[var][0], arg)
					else:
						self.var_set[var][0][var] = arg

					print(var+" is now "+self.var_set[var][0][var])
					break
			if not found:
				return "Unknown field \""+args[0]+"\""

		else:
			return "not enough args"

	def description(self):
		return "sets value of [field]\nfield is caseinsensitive\n\nAvailable fields:\n"+"\n".join(self.var_set)

	def id(self):
		return "set"

	def usage(self):
		return "set [field] [value]"

class cmd_get_vars(cmd):
	def __init__(self, var_set):
		self.var_set = var_set

	def run(self, args):
		if len(args)==1:
			found = False
			for var in self.var_set:
				if var.lower()==args[0].lower():
					found = True
					print(var+": "+self.var_set[var][0][var])
					break
			if not found:
				return "Unknown field \""+args[0]+"\""
		else:
			return "Too many args"

	def description(self):
		return "prints current value of [field]\nfield is caseinsensitive\n\nAvailable fields:\n"+"\n".join(self.var_set)

	def id(self):
		return "get"

	def usage(self):
		return "get [field]"

class cmd_ls(cmd):
	def run(self, args):
		arg = " ".join(args)
		files = dir_relevant(arg)

		for i, file in enumerate(files):
			print(i+1, file)

	def description(self):
		return "Lists all relevant files in [dir]\nTracks could be imported using addi"

	def usage(self):
		return "ls [dir]"

	def id(self):
		return "ls_dir"

class cmd_fam_ls(cmd_unary):
	def __init__(self, name, List, desc = "all elements"):
		self.List =List
		self.name = name
		self.desc = desc

	def _run(self):
		for i,e in enumerate(self.List):
			print(f"{i+1:02}. "+ str(e))

	def id(self):
		return self.name

	def description(self):
		return "Lists " + self.desc

class cmd_length(cmd_unary):
	def _run(self):
		print(Tracks_length(new_state["Tracks"]))

	def id(self):
		return "length"

	def description(self):
		return "Prints length of album eg. all currently loaded Tracks"

class cmd_rm_all(cmd_unary):
	def _run(self):
		for track in reversed(new_state["Tracks"]):
			track_rm(new_state, track)

	def description(self):
		return "Clears Tracklist"

	def id(self):
		return "rm_all"

class cmd_reorder(cmd_unary):
	def _run(self):
		file = open("order.txt", "w")
		file.write("\n".join([i.name for i in new_state["Tracks"]]))
		file.close()
		print("waiting for editor to close")
		start = datetime.now()
		if os.name=="nt":
			process = subprocess.Popen(["start", "/WAIT", "order.txt"], shell=True)
			process.wait()
		else:
			subprocess.call(('xdg-open', "order.txt"))
		end = datetime.now()

		if (end-start).total_seconds()<1:
			print("Autodetection failed! Press Enter resume")
			input()

		print("Reading File!")
		lines = open("order.txt", "r").read().split("\n")
		for index, name in enumerate(lines):
			print(str(index+1)+". "+ name)
			track = getTrackByName(new_state["Tracks"], name)
			if track == None:
				return "Track could not be found \""+name+"\", don't change the names"
			else:
				track.index=index+1
		file.close()
		os.remove("order.txt")
		Tracks_sort(new_state["Tracks"])

	def description(self):
		return "Promts reorder dialouge\nChange the order of the Tracks inside the editor, save, and quit"

	def id(self):
		return "reorder"

class cmd_all(cmd_unary):
	def _run(self):
		for module in modules:
			module_run(current_states[module.name], new_state, module)

	def id(self):
		return "all"

	def description(self):
		return "Run all available modules in sequence"

class cmd_forward_arg(cmd):
	def __init__(self, name, desc, arg, func, args):
		self.func=func
		self.args=args
		self.name=name
		self.desc=desc
		self.arg=arg

	def run(self, args):
		arg = " ".join(inp[1:])
		return self.func(*self.args, arg)

	def description(self):
		return self.desc

	def id(self):
		return self.name

	def usage(self):
		return self.name + " ["+self.arg+"]"

class cmd_reset(cmd):
	def run(self, args):
		global new_state
		for module in modules:
			if module.name in args:
				Reset(module)
				args.remove(module.name)

		if "main" in args:
			new_state=conf_default()
			args.remove("main")
		if len(args):
			return "Unknown module \""+"\"\nUnknown module \"".join(args)+"\""

	def id(self):
		return "reset"
	def description(self):
		return "resets the states of all listed modules\nModules:\n"+"\n".join([i.name for i in modules])+"\nmain"

	def usage(self):
		return "reset [module...]"

class cmd_addi(cmd):
	def run(self, args):
		if len(args)<2:
			return "Too few args"

		errors = []
		files=dir_relevant(args[0])
		for i in args[1:]:
			index=int(i)-1
			if index<len(files):
				track_add(new_state, os.path.join(args[0], files[index]))
			else:
				errors.append(i)
		if len(errors):
			return ", ".join(errors) + " index is out of range"

	def id(self):
		return "addi"

	def description(self):
		return "adds files from [dir] by indecies"

	def usage(self):
		return "addi [path] [index...]"

commands = [cmd_fam_ls("ls", new_state["Tracks"], "all loaded Tracks"), cmd_ls(), cmd_fam_ls("ls_mod", modules, "all available modules"),
			cmd_fam_ls("ls_rm", new_state["removed"], "backlisted tracks\nuse add to remove track from blacklist"), cmd_fam_ls("ls_mon", new_state["dirs"], "currently monitored directories"),
			cmd_forward_arg("add", "loads new Track from path", "path", track_add, [new_state]),
			cmd_forward_arg("add_dir", "adds directory to monitoring list eg. loads all current and future Tracks from this directory", "path", dir_add, [new_state, True]),
			cmd_forward_arg("add_all", "loads all Tracks from directory, but doesn't start monitoring", "path", dir_add, [new_state, False]), cmd_forward_arg("rm", "unloads Track with name", "name", track_rmn, [new_state]),
			cmd_forward_arg("rm_dir", "unloads all tracks from this directory, stops monitoring", "path", dir_rm, [new_state]),
			cmd_forward_arg("rmi", "unloads Track with index", "index", track_rmi, [new_state]), cmd_reset(), cmd_addi(),
			cmd_get_vars(var_set), cmd_set_vars(var_set),
			cmd_rm_all(), cmd_length(), cmd_reorder(), cmd_all(), 
			cmd_save(), cmd_detect(), cmd_check()
			
			]

quits = ["q", "quit", "exit"]

run = True
while run:
	inp = input("PPublish: ~$ ").split( " " )
	cmd = inp[0].lower()
	Found = True
	if cmd in quits:
		run = False
	elif cmd == "help":
		print("Help for PPublish by NoHamster")
		print("Exit with " + ", ".join(quits))
		print("Commands:")
		print("Execute via shell")
		print("---------")
		for cmd in commands:
			print(cmd.id()+":")
			print("\t"+cmd.usage())
			print()
			print("\t"+cmd.description().replace("\n", "\n\t"))
		print("---------")
		print()


		print("Modules:")
		print("can also be called through the shell")
		print("---------")
		for module in modules:
			print(module.name + " - " + module.description())
		print("---------")
		print()

		print("Setting fields:")
		print("View or Change these with 'get' and 'set'")
		print("---------")
		for var in var_set:
			print(var)
		print("---------")
		print()

	else:
		Found=False
		for command in commands:
			if cmd==command.id().lower():
				error = command.run(inp[1:])
				if error:
					print("An error occured while executing command:")
					print("[ERROR] " + command.id() + ": " + str(error))
					print("use 'help' if your unsure of usage")
				Found=True

		if not Found:
			for module in modules:
				if cmd == module.name:
					module_run(current_states[module.name], new_state, module)
					Found=True
					break

	if not Found:
			print("[ERROR] Unknown command \"" + cmd + "\"")

	pub_save()
pub_save()

