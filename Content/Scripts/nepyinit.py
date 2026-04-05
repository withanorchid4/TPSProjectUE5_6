# -*- encoding: utf-8 -*-
import ue
import traceback

def on_init():
	ue.LogWarning('hello, nepy!')
	if ue.GIsEditor:
		try:
			import reload_monitor
			reload_monitor.start()
		except:
			traceback.print_exc()
		try:
			import gmcmds
			gmcmds.debug()
		except:
			traceback.print_exc()
	
	import character # noqa

def on_shutdown():
	ue.LogWarning('bye, nepy!')

def on_debug_input(cmd_str):
	import gmcmds
	return gmcmds.handle_debug_input(cmd_str)

def on_tick(dt):
	pass