# Project TODO List
### For the week
- [ ] get add song enabled and start on that window (song window)
- [X] change go live to circle that is red when on and no fill when off
- [ ] change undo redo to arrows
- [X] change preview size to 1x,2x,3x etc
- [ ] media pool toggle
- [X] move load save recents into a drop down file / project dropdown 
- [X] move settings and edit templates up there too ^
- [X] make a settings window (setup the OpenSource/Pro toggle/Dev toggle) (add logic still need)
- [X] Chage edit template to templates
- [X] Check if the monitor selectors are working on windows
- [X] add collapseable for benchmarks
- [X] set the Icon for the different OSs
- [ ] find a fast dictionary search highlighting or what modern things do
- [X] rereferance the app_settings.json file for the settings


# Existing windows
## Template Editor - Layout Tab Enhancements
- [X] Renaming existing layouts (add logic still)
- [ ] Changing layout background color
- [ ] Setup a color so they can be colorcoded for quick identification
- [ ] Add a list of text boxes so if one gets sent to the ether they can delete it
### Low Prio
- [ ] Locking/Unlocking text boxes (prevent move/resize)
- [ ] Refactor: Pull Layout tab functionality into a separate Python file/module
- [ ] Move textbox buttons above the editing area (error after moving, prob in ui file)
- [ ] Adding Rulers to the layout preview
- [ ] Check on windows if the cursor changes on hover the drag points

## Output window
- [ ] Update the template info

## Main Window - Slides
- [ ] Get the slides working with the new templates
- [ ] Make a Song creation window
- [ ] Add recent projects button
- [ ] Add a timer rotation button on the section bar

## Other Fucntionality
- [ ] Black magic Deck link card integration
- [ ] ^ C#/C++ dll for BM Decklink
- [ ] Medium term cacheing thumbnails
- [ ] better error handling when hovering over slide error (use the warning in output)
- [ ] add a media pool and a way to clean it up or at least a space usage


# New Windows
## Song creation window
- [ ] Button for adding simple lyrics (empty line with \n = new slide)
- [ ] Button / tab for adding quick Title /  Attribution
- [ ] Color code templates (to quickly ID if wrong template on slide)
- [ ] Drag and drop images
- [ ] add back lightweight spellcheck at least / custom dictionary
- [ ] Songs vertical layout on left, large text center, controls right (add types/template)
### Low Prio
- [ ] Add something for showing attribution (defalt attribution / title templates for quick adding)
- [ ] add a custom delimiter ("#.", "\")

## Settings window
- [ ] Open source / Pro / Dev toggle
- [ ] place to set what the default templates and styles are
- [X] Add program Load time stats back
- [ ] Default Card background color (allow for transparent and checkerboard)
- [X] Move screen selection into the settings window


# Long term goals
- [ ] PP, proP importing
- [ ] Transitions
- [ ] maybe output preview? (if it's still feeling light weight)
