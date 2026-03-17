# Seznam ID prvků (strings)
id_list = ["1042647", "1347539", "1347540", "1356982", "1356983", "1356984", "1356983", "1356982", "1357028", "1357027", "1042662", "3409520", "1042663", "1042664", "10000001", "1357005", "1357004", "1357003", "3391747", "3391748", "3391747", "1357003", "1357002", "1042706", "1042705", "1042704", "1042703", "1042702", "3409518", "3409519", "3409518", "1042702", "1042701", "1042702", "1042703", "1042704", "1042705", "1042706", "1357002", "1357003", "1357004", "1357005", "10000001", "1357006", "10000001", "1042665", "1042666", "2143721", "2143722", "2143723", "2143724", "2143725", "10000002", "1042641", "1042642", "1042641", "10000002", "2143725", "2143724", "2143723", "2143722", "2143721", "3391844", "3391843", "1357007", "1357006", "1357007", "1042634", "1042635", "1042636", "1042637", "1042638", "1042639", "1042640", "10000002", "2143726", "3391876", "1042642", "1042538", "1042553", "1042552", "1042551", "1042550", "1042549", "1042548", "1042547", "1042546", "1042545", "1042544", "1042543", "1042542", "3494295", "1042666", "1356998", "1356997", "3776930", "1356997", "1356996", "1042471", "1042470", "1042593", "1357030", "1357029", "1357030", "1042593", "1042592", "1042650", "1347536", "1042539", "1347537", "1042701", "1347538", "1042647"]

# Aktivní vrstva
layer = iface.activeLayer()

# Začneme editaci vrstvy
layer.startEditing()

# Projdeme seznam a aktualizujeme atribut 'poradi'
for index, feat_id in enumerate(id_list, start=1):
    # Najdeme všechny prvky s tímto ID
    expr = f'"source" = {feat_id}'
    request = QgsFeatureRequest(QgsExpression(expr))

    for feat in layer.getFeatures(request):
        # Současná hodnota atributu
        current_value = feat["poradi"]
        if current_value is None or current_value == "":
            new_value = str(index)
        else:
            new_value = f"{current_value} | {index}"

        # Zapíšeme novou hodnotu
        layer.changeAttributeValue(
            feat.id(),
            layer.fields().indexFromName('poradi'),
            new_value
        )

# Uložíme změny
layer.commitChanges()
print("Atributy byly aktualizovány s připojením.")
