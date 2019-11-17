
$(document).ready(function() {

	$('[data-toggle="tooltip"]').tooltip();


	/* Clear result after form submit */
	$("body").on("submit", "form.form-mpk", function(event) {
		var div_result = $("body").find("div.mpk-result");
		div_result.html("Loading..");
	});

});

