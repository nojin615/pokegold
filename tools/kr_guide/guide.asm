; Guide menu for the Korean Gold/Silver mod (START menu '공략') — tools/kr_guide.py assembles this with
; rgbasm together with the generated kr_syms.inc (Korean ROM addresses) and guide_data.inc (texts, tables).
;
; - bank 4 (free tail): a 10-entry copy of the START menu item table (+ '공략' as item 9), the item's
;   function (FadeToMenu -> farcall GuideMain -> CloseSubmenu, like the trainer card) and two list hooks:
;   '공략' right after '가방', and '닫다' only while the menu has fewer than 8 items (8 fill the screen).
; - GUIDE_BANK: GuideMain — a full-screen list (이 맵 출현 / 전설과 환상 / 다음 목표 / 도감 안내) drawn
;   like the options screen (Textbox + PlaceString, hBGMapMode 1), A opens a page, B goes back.
;   Korean glyphs are 8x16: PlaceString at tile row r draws rows r-1 and r, so text goes on rows 2, 5, 7, ... 15;
;   line break inside a string = $59 (kr_guide.py NEXT).
; - Pages with more than one screen (전설과 환상, 도감 안내): A / down / right = next screen, up / left = back,
;   B = back to the list (A on the last screen too).
; - Scratch RAM while the guide is open: wStringBuffer1 (9 bytes).

INCLUDE "kr_syms.inc"

DEF SCREEN_W EQU 20
MACRO hlcoord
	ld hl, wTilemap + SCREEN_W * (\2) + (\1)
ENDM

DEF PAD_A     EQU $01
DEF PAD_B     EQU $02
DEF PAD_RIGHT EQU $10
DEF PAD_LEFT  EQU $20
DEF PAD_UP    EQU $40
DEF PAD_DOWN  EQU $80
DEF CURSOR_TILE EQU $ED     ; '▶' (single-byte charmap)
DEF BLANK_TILE  EQU $7F
DEF MENU_ROW    EQU 5
DEF CURSOR_COL  EQU 2
DEF LIST_LINES  EQU 6       ; rows 5, 7, ... 15
DEF DONE_COL    EQU 16
DEF ROAM_PLACE_COL EQU 6
DEF WILD_BODY_ROW EQU 4     ; 이 맵 출현: 7 body lines on rows 4, 6, ... 16 (title on row 2)
DEF MARK_TILE   EQU $60     ; '■' before a caught species (the Emerald guide marks them with a red square)
DEF NEXT_CHAR   EQU $59     ; kr_guide.py NEXT
DEF NUM_SPECIES EQU 251

DEF wGuideSkip    EQU wStringBuffer1
DEF wGuideSpecies EQU wStringBuffer1 + 1
DEF wGuideLines   EQU wStringBuffer1 + 2
DEF wGuideEntry   EQU wStringBuffer1 + 3   ; 2 bytes

SECTION "KRGuideBank4", ROMX[BANK4_FREE], BANK[4]

GuideMenuItems::
	ORIGINAL_START_MENU_ITEMS          ; the 9 original entries (func, string, description)
	dw GuideItem, GuideItemString, GuideItemDesc

GuideItem:
	call FadeToMenu
	ld a, BANK(GuideMain)
	ld hl, GuideMain
	rst FarCall
	call CloseSubmenu
	ld a, 0                            ; back to the START menu (as the trainer card does)
	ret

GuidePackHook::                        ; replaces 'ld a, PACK / call AppendMenuList'
	ld a, 2
	call AppendMenuList
	ld a, 9
	jp AppendMenuList

GuideExitHook::                        ; replaces 'ld a, EXIT / call AppendMenuList'
	ld a, c
	cp 8
	ret nc
	ld a, 6
	jp AppendMenuList

GuideItemString:
	GUIDE_ITEM_STRING
GuideItemDesc:
	GUIDE_ITEM_DESC

SECTION "KRGuide", ROMX[$4000], BANK[GUIDE_BANK]

GuideMain::
	ldh a, [hInMenu]
	push af
	ld a, 1
	ldh [hInMenu], a
	call ClearBGPalettes
	ld c, 0
.redraw
	push bc
	call DrawMenu
	pop bc
	push bc
	call PutCursor
	call ShowScreen
	pop bc
.loop
	push bc
	call JoyTextDelay
	pop bc
	ldh a, [hJoyPressed]
	bit 1, a
	jr nz, .exit
	bit 0, a
	jr nz, .open
	bit 6, a
	jr nz, .up
	bit 7, a
	jr z, .loop
	inc c
	ld a, c
	cp NUM_PAGES
	jr c, .move
	ld c, 0
	jr .move
.up
	ld a, c
	and a
	jr nz, .dec
	ld c, NUM_PAGES
.dec
	dec c
.move
	push bc
	call ClearCursors
	pop bc
	push bc
	call PutCursor
	pop bc
	jr .loop
.open
	push bc
	ld a, c
	call OpenPage
	pop bc
	jr .redraw
.exit
	pop af
	ldh [hInMenu], a
	ret

ShowScreen:
	ld a, 1
	ldh [hBGMapMode], a
	call WaitBGMap
	ld b, SCGB_DIPLOMA
	call GetSGBLayout
	jp SetDefaultBGPAndOBP

Frame:
	hlcoord 0, 0
	ld b, 16
	ld c, 18
	jp Textbox

FrameTitle:                            ; de = title
	push de
	call Frame
	pop de
	hlcoord 2, 2
	jp PlaceString

DrawMenu:
	ld de, TxtGuideTitle
	call FrameTitle
	hlcoord CURSOR_COL + 2, MENU_ROW
	ld de, TxtMenuItems
	jp PlaceString

CursorAddr:                            ; c = row index -> hl
	ld a, c
RowAddr:                               ; a = line (0-5) -> hl = column 2 of row 5 + 2 a
	hlcoord CURSOR_COL, MENU_ROW
	ld de, SCREEN_W * 2
.next
	and a
	ret z
	add hl, de
	dec a
	jr .next

PutCursor:
	call CursorAddr
	ld [hl], CURSOR_TILE
	ret

ClearCursors:
	ld c, NUM_PAGES
.loop
	dec c
	push bc
	call CursorAddr
	ld [hl], BLANK_TILE
	pop bc
	ld a, c
	and a
	jr nz, .loop
	ret

WaitAB:
	call JoyTextDelay
	ldh a, [hJoyPressed]
	and PAD_A | PAD_B
	jr z, WaitAB
	ret

OpenPage:                              ; a = page
	ld e, a
	ld d, 0
	ld hl, .pages
	add hl, de
	add hl, de
	ld a, [hli]
	ld h, [hl]
	ld l, a
	jp hl
.pages
	dw PageWild, PageLegends, PageGoal, PageDex

; hl = draw routine (c = screen, returns carry when there are more screens after it)
Pager:
	ld c, 0
.draw
	push hl
	push bc
	call .call_hl
	pop bc
	pop hl
	ld b, 0
	jr nc, .last
	inc b
.last
	push hl
	push bc
	call WaitBGMap
	pop bc
	pop hl
.key
	push hl
	push bc
	call JoyTextDelay
	pop bc
	pop hl
	ldh a, [hJoyPressed]
	bit 1, a
	ret nz
	bit 0, a
	jr z, .not_a
	ld a, b
	and a
	ret z                              ; A on the last screen: back
	jr .next
.not_a
	and PAD_DOWN | PAD_RIGHT
	jr nz, .down
	ldh a, [hJoyPressed]
	and PAD_UP | PAD_LEFT
	jr z, .key
	ld a, c
	and a
	jr z, .key
	dec c
	jr .draw
.down
	ld a, b
	and a
	jr z, .key
.next
	inc c
	jr .draw
.call_hl
	jp hl

; 이 맵 출현: the map's table pages (kr_guide.py wild_pages — made at build time, in the WILD banks): FindWild gives the
; bank and the page list (db pages / per page dw title, body, marks); each screen is drawn with FarPlaceString (bank 0) and the
; marks list (db line, species ... $FF) puts MARK_TILE before every caught species (column 1 of body line `line`)
PageWild:
	ld a, [wMapGroup]
	ld b, a
	ld a, [wMapNumber]
	ld c, a
	call FindWild
	jr nc, .found
	ld de, TxtWildTitle
	call FrameTitle
	hlcoord 2, 5
	ld de, TxtNoWild
	call PlaceString
	call WaitBGMap
	jp WaitAB
.found                                 ; hl -> db bank / dw page list
	ld a, [hli]
	ld [wGuideSpecies], a              ; bank of this map's pages
	ld a, [hli]
	ld h, [hl]
	ld l, a
	ld a, l
	ld [wGuideEntry], a
	ld a, h
	ld [wGuideEntry + 1], a
	ld a, [wGuideSpecies]
	call GetFarByte
	ld [wGuideLines], a                ; number of pages
	ld hl, WildScreen
	jp Pager

WildScreen:                            ; c = page -> carry when more pages follow
	push bc
	call Frame
	pop bc
	push bc
	ld a, [wGuideEntry]                ; hl = page list + 1 + 6 c
	ld l, a
	ld a, [wGuideEntry + 1]
	ld h, a
	inc hl
	ld a, c
	add a
	ld e, a
	add a
	add e
	ld e, a
	ld d, 0
	add hl, de
	call FarWord                       ; title
	push hl
	hlcoord 2, 2
	ld a, [wGuideSpecies]
	call FarPlaceString
	pop hl
	call FarWord                       ; body
	push hl
	hlcoord 1, WILD_BODY_ROW
	ld a, [wGuideSpecies]
	call FarPlaceString
	pop hl
	call FarWord                       ; marks
	ld h, d
	ld l, e
.mark
	ld a, [wGuideSpecies]
	call GetFarByte
	cp $FF
	jr z, .marks_done
	inc hl
	push hl
	ld hl, wTilemap + SCREEN_W * WILD_BODY_ROW + 1
	ld de, SCREEN_W * 2
	and a
.row
	jr z, .at_row
	add hl, de
	dec a
	jr .row
.at_row
	ld b, h
	ld c, l
	pop hl
	ld a, [wGuideSpecies]
	call GetFarByte                    ; species
	inc hl
	push hl
	push bc
	dec a
	call CheckCaught
	pop bc
	pop hl
	jr z, .mark
	ld a, MARK_TILE
	ld [bc], a
	jr .mark
.marks_done
	pop bc
	ld a, c
	inc a
	ld hl, wGuideLines
	cp [hl]                            ; carry when c + 1 < pages
	ret

FarWord:                               ; de = the word at [wGuideSpecies]:hl, hl += 2
	ld a, [wGuideSpecies]
	call GetFarByte
	ld e, a
	inc hl
	ld a, [wGuideSpecies]
	call GetFarByte
	ld d, a
	inc hl
	ret

FindWild:                              ; b = map group, c = map number -> hl = its bank byte (nc) or carry
	ld hl, WildIndex
.loop
	ld a, [hli]
	cp $ff
	jr z, .none
	cp b
	jr nz, .skip1
	ld a, [hli]
	cp c
	ret z                              ; (carry clear: cp gave equal)
	inc hl
	inc hl
	inc hl
	jr .loop
.skip1
	inc hl
	inc hl
	inc hl
	inc hl
	jr .loop
.none
	scf
	ret

; 전설과 환상: the fixed legends (done when their object's flag is set) and the three roaming beasts (where now)
PageLegends:
	ld hl, LegendScreen
	jp Pager

LegendScreen:                          ; c = screen
	push bc
	ld de, TxtLegendTitle
	call FrameTitle
	pop bc
	ld a, c                            ; hl = LegendTable + 6 * (6 c)
	add a
	ld b, a
	add a
	add b
	ld l, a
	ld h, 0
	ld d, h
	ld e, l
	add hl, hl
	add hl, de
	add hl, hl
	ld de, LegendTable
	add hl, de
	xor a
	ld [wGuideLines], a
.loop
	ld a, [hl]
	cp $ff
	jr z, .end                         ; (carry clear)
	ld a, [wGuideLines]
	cp LIST_LINES
	jr z, .more
	ld a, l
	ld [wGuideEntry], a
	ld a, h
	ld [wGuideEntry + 1], a
	call LegendLine
	ld hl, wGuideLines
	inc [hl]
	call LoadEntry
	ld de, 6
	add hl, de
	jr .loop
.more
	scf
.end
	ret

LoadEntry:                             ; hl = [wGuideEntry]
	ld a, [wGuideEntry]
	ld l, a
	ld a, [wGuideEntry + 1]
	ld h, a
	ret

; entry: db kind (0 fixed, 1 roaming); dw text; dw address; db mask
; fixed: address/mask = its event flag; roaming: address = its roam struct (species, level, group, number)
LegendLine:
	call LoadEntry
	inc hl
	ld a, [hli]
	ld e, a
	ld d, [hl]
	push de
	ld a, [wGuideLines]
	call RowAddr
	pop de
	call PlaceString
	call LoadEntry
	ld a, [hli]
	and a
	jr nz, .roaming
	inc hl
	inc hl
	ld a, [hli]
	ld e, a
	ld a, [hli]
	ld d, a
	ld a, [de]
	and [hl]
	ret z
.done
	ld a, [wGuideLines]
	call RowAddr
	ld de, DONE_COL - CURSOR_COL
	add hl, de
	ld de, TxtDone
	jp PlaceString
.roaming
	inc hl
	inc hl
	ld a, [hli]
	ld h, [hl]
	ld l, a
	ld a, [hli]                        ; species (0 = not out yet, or caught / defeated)
	and a
	jr z, .gone
	inc hl
	ld a, [hli]
	ld b, a
	ld c, [hl]
	call FindWild
	ret c
	ld de, 8
	add hl, de
	ld a, [hli]
	ld d, [hl]
	ld e, a
	jr .place
.gone
	ld a, [RELEASED_ADDR]
	and RELEASED_MASK
	jr nz, .done
	ld de, TxtNotYet
.place
	push de
	ld a, [wGuideLines]
	call RowAddr
	ld de, ROAM_PLACE_COL - CURSOR_COL
	add hl, de
	pop de
	jp PlaceString

; 다음 목표: the first goal whose RAM bit (event flag or badge) is not set yet
PageGoal:
	ld de, TxtGoalTitle
	call FrameTitle
	ld hl, GoalTable
.loop
	ld a, [hli]
	ld e, a
	ld a, [hli]
	ld d, a
	or e
	jr z, .show                        ; end: dw 0, dw the 'all done' text
	ld a, [de]
	and [hl]
	inc hl
	jr z, .show
	inc hl
	inc hl
	jr .loop
.show
	ld a, [hli]
	ld d, [hl]
	ld e, a
	hlcoord 2, 5
	call PlaceString
	call WaitBGMap
	jp WaitAB

; 도감 안내: species not caught yet, each with where to get it (strings made at build time)
PageDex:
	ld hl, DexScreen
	jp Pager

DexScreen:                             ; c = screen
	push bc
	ld de, TxtDexTitle
	call FrameTitle
	pop bc
	ld a, c
	add a
	ld b, a
	add a
	add b
	ld [wGuideSkip], a                 ; 6 c uncaught species before this screen
	xor a
	ld [wGuideSpecies], a              ; species - 1
	ld [wGuideLines], a
.loop
	ld a, [wGuideSpecies]
	cp NUM_SPECIES
	jr nc, .end
	call CheckCaught
	jr nz, .next
	ld a, [wGuideLines]
	cp LIST_LINES
	jr z, .more
	ld a, [wGuideSkip]
	and a
	jr z, .show
	dec a
	ld [wGuideSkip], a
	jr .next
.show
	ld a, [wGuideLines]
	call RowAddr
	push hl
	ld a, [wGuideSpecies]
	ld e, a
	ld d, 0
	ld hl, DexStrings
	add hl, de
	add hl, de
	ld a, [hli]
	ld d, [hl]
	ld e, a
	pop hl
	call PlaceString
	ld hl, wGuideLines
	inc [hl]
.next
	ld hl, wGuideSpecies
	inc [hl]
	jr .loop
.more
	scf
	ret
.end
	ld a, [wGuideLines]
	and a
	ret nz                             ; (carry clear)
	hlcoord 2, 5
	ld de, TxtDexAll
	call PlaceString
	and a
	ret

CheckCaught:                           ; a = species - 1 -> nz when caught
	ld b, a
	and 7
	ld c, a
	ld a, b
	srl a
	srl a
	srl a
	ld e, a
	ld d, 0
	ld hl, wPokedexCaught
	add hl, de
	ld a, [hl]
	inc c
.shift
	dec c
	jr z, .bit
	rrca
	jr .shift
.bit
	and 1
	ret

INCLUDE "guide_data.inc"

; bank 0 (free bytes): place a string of another ROM bank — the guide bank cannot switch itself out
SECTION "KRGuideHome", ROM0[HOME_FREE]
FarPlaceString:                        ; a = bank, de = string, hl = tilemap
	ld b, a
	ldh a, [hROMBank]
	push af
	ld a, b
	rst $10                            ; Bankswitch
	call PlaceString
	pop af
	rst $10
	ret

INCLUDE "wild_data.inc"
