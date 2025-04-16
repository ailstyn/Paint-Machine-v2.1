# To-Do Checklist

This document tracks the tasks for the Paint Machine v2 project.

## General Tasks
- [x] Set up project folder structure
- [x] Implement Arduino code for HX711 and relay control
- [x] Implement Raspberry Pi communication with Arduinos
- [X] Create GUI using Tkinter
- [X] Test communication between Raspberry Pi and Arduinos
- [ ] Calibrate load cells and update `config.txt`
- [ ] Finalize GUI design
- [ ] Add error handling for edge cases
- [ ] Add Spanish language labels
- [ ] Implement USB power control:
  - [ ] Enable USB power control by adding `dtoverlay=dwc2,dr_mode=host` to `/boot/config.txt`
  - [X] Write a function to disable USB power on shutdown
  - [X] Call the USB power-off function in the `finally` block of the main program
  - [ ] Test USB power-off functionality

## Documentation
- [x] Add Bill of Materials (BOM)
- [x] Add To-Do Checklist
- [ ] Write user manual for the system
- [ ] Document wiring and hardware setup

## Testing
- [ ] Test relay activation via button press
- [ ] Test target weight request and response
- [ ] Verify GUI functionality
- [ ] Perform end-to-end system testing