(function () {
    "use strict";

    function setupImageFormset(root) {
        const prefix = root.dataset.prefix;
        const rowsContainer = root.querySelector("[data-image-formset-rows]");
        const template = root.querySelector("[data-image-formset-template]");
        const totalFormsInput = document.querySelector("#id_" + prefix + "-TOTAL_FORMS");
        const addButton = root.querySelector("[data-image-formset-add]");

        if (!rowsContainer || !template || !totalFormsInput) {
            return;
        }

        function visibleRows() {
            return Array.from(rowsContainer.querySelectorAll("[data-image-formset-row]")).filter(function (row) {
                return row.style.display !== "none";
            });
        }

        function renumberLabels() {
            visibleRows().forEach(function (row, index) {
                const counter = row.querySelector("[data-image-formset-counter]");
                if (counter) {
                    counter.textContent = String(index + 1);
                }
            });
        }

        function bindRemove(row) {
            const button = row.querySelector("[data-image-formset-remove]");
            if (!button) {
                return;
            }
            button.addEventListener("click", function () {
                const deleteInput = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (deleteInput) {
                    deleteInput.checked = true;
                    row.style.display = "none";
                } else {
                    row.remove();
                    const newTotal = rowsContainer.querySelectorAll("[data-image-formset-row]").length;
                    totalFormsInput.value = String(newTotal);
                }
                renumberLabels();
            });
        }

        rowsContainer.querySelectorAll("[data-image-formset-row]").forEach(bindRemove);

        if (addButton) {
            addButton.addEventListener("click", function () {
                const nextIndex = parseInt(totalFormsInput.value, 10) || 0;
                const html = template.innerHTML
                    .replace(/__index__/g, String(nextIndex))
                    .replace(/__counter__/g, String(visibleRows().length + 1));
                const wrapper = document.createElement("div");
                wrapper.innerHTML = html.trim();
                const newRow = wrapper.querySelector("[data-image-formset-row]");
                if (!newRow) {
                    return;
                }
                rowsContainer.appendChild(newRow);
                totalFormsInput.value = String(nextIndex + 1);
                bindRemove(newRow);
                renumberLabels();
            });
        }

        renumberLabels();
    }

    function init() {
        document.querySelectorAll("[data-image-formset]").forEach(setupImageFormset);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
