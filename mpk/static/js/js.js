
$(document).ready(function() {

	$('[data-toggle="tooltip"]').tooltip();


	/* Clear result after form submit */
	$("body").on("submit", "form.form-mpk", function(event) {
		var tr_form_errors = $("body").find("tr.form-errors");
		var div_result = $("body").find("div.mpk-result");

		tr_form_errors.empty();
		div_result.html("Loading..");
	});

});

