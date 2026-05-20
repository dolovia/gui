var separateur="###";


function getFormTableau() {
  var f;
  for (i=0;i<document.forms.length;i++) {
     if (document.forms[i].actionTableau) f = document.forms[i];
  }
  return f;
}


function setAction(action) {
  var form = getFormTableau();
  form.actionTableau.value=action;
  form.submit();
}

function setEventValue(valeur) {
  var form = getFormTableau();
  form.eventValue.value = valeur;
}

function selectLineByKey(action,elementKey) {
   setEventValue(elementKey);
   setAction(action);
}	

function fselectioncolonne(elementKey,action) {
   setEventValue(elementKey);
   setAction(action);
}

function supprimer() {
	if (window.confirm("Etes-vous sûr de vouloir supprimer les lignes sélectionnées ?")) {
		setAction('suppression'+separateur+'eventValue');
	}
}

function modification() {
   setAction('modification'+separateur+'eventValue');
}

function selection() {
   setAction('selection'+separateur+'eventValue');
}
