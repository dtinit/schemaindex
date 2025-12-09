(() => {
  // This needs to match the animation duration in site.css
  const MESSAGE_TIMEOUT_MS = 10 * 1000;

  /**
   * @param {(...args: any) => any} fn
   * @param {Parameters<typeof setTimeout>[1]} time
   */
  const debounce = (fn, time) => {
    /** @type ReturnType<typeof setTimeout> */
    let timeout;
    /** @param {Parameters<typeof fn>} args */
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn(...args), time);
    };
  };

  document.addEventListener('DOMContentLoaded', () => {
    Array.from(document.querySelectorAll('.js-autosubmit-input'))
      // If the input isn't in a form, there's nothing to submit
      .filter(
        /** @returns {input is (HTMLInputElement & {form: HTMLFormElement})} */
        (input) => input instanceof HTMLInputElement && Boolean(input.form)
      )
      .forEach((input) => {
        const handleChange = () => {
          input.form.submit();
        };
        const debouncedChangeHandler = debounce(handleChange, 500);
        input.addEventListener('input', debouncedChangeHandler);
        // When the page refreshes, we want the cursor at the end of the input value
        if (input.hasAttribute('autofocus')) {
          input.selectionStart = input.value.length;
        }
      });

    Array.from(
      document.querySelectorAll('.message__dismissal-trigger')
    ).forEach((element) => {
      element.addEventListener('click', () => {
        if (element.parentElement) {
          element.parentElement.remove();
        }
      });
    });

    Array.from(
      document.querySelectorAll('[data-formset-append-to-list-id]')
    ).forEach((appendTriggerElement) => {
      const formsetListId = appendTriggerElement.getAttribute(
        'data-formset-append-to-list-id'
      );
      if (!formsetListId) {
        return;
      }
      const formsetListElement = document.querySelector(
        `[data-formset-list-id="${formsetListId}"]`
      );
      if (!formsetListElement) {
        return;
      }
      const emptyFormTemplate = document.querySelector(
        `[data-formset-template-for-id="${formsetListId}"]`
      );
      if (!emptyFormTemplate) {
        return;
      }
      appendTriggerElement.addEventListener('click', () => {
        const currentFormItemCount =
          formsetListElement.querySelectorAll('.formset').length;
        const nextFormItemHtml = emptyFormTemplate.innerHTML.replace(
          /__prefix__/g,
          currentFormItemCount.toString()
        );
        formsetListElement.insertAdjacentHTML('beforeend', nextFormItemHtml);
        const totalFormInput = formsetListElement.querySelector(
          `input[name="${formsetListId}-TOTAL_FORMS"]`
        );
        if (totalFormInput instanceof HTMLInputElement) {
          totalFormInput.value = (currentFormItemCount + 1).toString();
        }
      });
    });

    Array.from(
      document.querySelectorAll('[data-formset-remove-from-list-id]')
    ).forEach((removeTriggerElement) => {
      const formsetListId = removeTriggerElement.getAttribute(
        'data-formset-remove-from-list-id'
      );
      if (!formsetListId) {
        return;
      }
      const formsetListElement = document.querySelector(
        `[data-formset-list-id="${formsetListId}"]`
      );
      if (!formsetListElement) {
        return;
      }
      const totalFormCountInput = formsetListElement.querySelector(
        `input[name="${formsetListId}-TOTAL_FORMS"]`
      );
      if (!(totalFormCountInput instanceof HTMLInputElement)) {
        return;
      }
      removeTriggerElement.addEventListener('click', () => {
        const formsetElements = Array.from(
          formsetListElement.getElementsByClassName('formset')
        );
        if (!formsetElements.length) {
          return;
        }
        formsetElements[formsetElements.length - 1].remove();
        const totalFormInput = formsetListElement.querySelector(
          `input[name="${formsetListId}-TOTAL_FORMS"]`
        );
        if (totalFormInput instanceof HTMLInputElement) {
          totalFormInput.value = (formsetElements.length - 1).toString();
        }
      });
    });

    setTimeout(() => {
      Array.from(document.querySelectorAll('.messages .message')).forEach(
        (element) => {
          element.remove();
        }
      );
    }, MESSAGE_TIMEOUT_MS);
  });
})();
