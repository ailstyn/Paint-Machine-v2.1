def startup(app, timer):
    # ...existing code...

    def open_filling_mode_dialog():
        print("[DEBUG] Creating SelectionDialog for filling mode")
        filling_modes = [("AUTO", app.tr("AUTO")), ("MANUAL", app.tr("MANUAL")), ("SMART", app.tr("SMART"))]
        def filling_mode_selected(mode, index):
            # ...existing code...
        filling_mode_dialog = SelectionDialog(
            options=filling_modes,
            parent=app,
            title=app.tr("SET FILLING MODE"),
            on_select=filling_mode_selected
        )
        app.active_dialog = filling_mode_dialog
        print("[DEBUG] Showing SelectionDialog")
        filling_mode_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        filling_mode_dialog.show()
        while filling_mode_dialog.isVisible():
            QApplication.processEvents()
            time.sleep(0.01)
        print(f"[DEBUG] SelectionDialog closed. wizard.isVisible={wizard.isVisible()}")
        app.active_dialog = wizard

    wizard = StartupWizardDialog(parent=app, num_stations=NUM_STATIONS, on_station_verified=open_filling_mode_dialog)
    app.active_dialog = wizard
    wizard.setWindowState(Qt.WindowState.WindowFullScreen)
    # ...existing code...
    wizard.exec()
    print(f"[DEBUG] StartupWizardDialog closed? isVisible={wizard.isVisible()}")