	object_const_def
	const SILVERCAVEROOM3_RED
	const SILVERCAVEROOM3_MEWTWO

SilverCaveRoom3_MapScripts:
	def_scene_scripts

	def_callbacks

Red:
	special FadeOutMusic
	faceplayer
	opentext
	writetext RedSeenText
	waitbutton
	closetext
	winlosstext RedWinLossText, RedWinLossText
	loadtrainer RED, RED1
	startbattle
	dontrestartmapmusic
	reloadmapafterbattle
	special FadeOutMusic
	opentext
	writetext RedLeavesText
	waitbutton
	closetext
	special FadeOutToBlack
	special ReloadSpritesNoPalettes
	disappear SILVERCAVEROOM3_RED
	pause 15
	special FadeInFromBlack
	pause 30
	special HealParty
	reanchormap
	credits
	end

RedSeenText:
	text "…"
	line "…"
	done

RedWinLossText:
	text "…"
	done

RedLeavesText:
	text "…"
	line "…"
	done

SilverCaveRoom3Mewtwo:
	faceplayer
	opentext
	writetext SilverCaveRoom3MewtwoText
	cry MEWTWO
	pause 15
	closetext
	loadwildmon MEWTWO, 70
	startbattle
	readvar VAR_BATTLERESULT
	ifequal DRAW, .Fled
	disappear SILVERCAVEROOM3_MEWTWO
.Fled:
	reloadmapafterbattle
	end

SilverCaveRoom3MewtwoText:
	text "Mew!"
	done

SilverCaveRoom3_MapEvents:
	db 0, 0 ; filler

	def_warp_events
	warp_event  9, 33, SILVER_CAVE_ROOM_2, 2

	def_coord_events

	def_bg_events

	def_object_events
	object_event  9, 10, SPRITE_RED, SPRITEMOVEDATA_STANDING_UP, 0, 0, -1, -1, PAL_NPC_RED, OBJECTTYPE_SCRIPT, 0, Red, EVENT_RED_IN_MT_SILVER
	; mod: Mewtwo moved here from Cerulean City (its spot there could not be reached)
	object_event 12, 10, SPRITE_MONSTER, SPRITEMOVEDATA_POKEMON, 0, 0, -1, -1, PAL_NPC_PINK, OBJECTTYPE_SCRIPT, 0, SilverCaveRoom3Mewtwo, EVENT_SILVER_CAVE_MEWTWO
