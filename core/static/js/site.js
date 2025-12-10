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

  /** @param {HTMLElement} formsetElement */
  const attachFormsetControlHandlers = (formsetElement) => {
    const closeTriggerElements = Array.from(
      formsetElement.getElementsByClassName('formset__close-trigger')
    );
    closeTriggerElements.forEach((element) => {
      element.addEventListener('click', () => {
        formsetElement.remove();
      });
    });
  };

  /**
   * Django formsets have an internal "management form" which tracks
   * the number of forms inside the formset. Rather than updating these
   * values manually as we add or remove forms, here we start watching
   * the formset's children so we can update the management form values
   * as we detect forms being added/removed.
   *
   * Note: this assumes all forms within an element with the
   * "data-formset-list-id" attribute have the ".formset" class.
   *
   * @param {HTMLElement} formsetListElement
   */
  const initializeFormsetListManagementForm = (formsetListElement) => {
    const formsetListId = formsetListElement.getAttribute(
      'data-formset-list-id'
    );
    if (!formsetListId) {
      console.error(
        new Error(
          "The formset list element has no 'data-formset-list-id' attribute"
        )
      );
      return;
    }
    const totalFormInput = formsetListElement.querySelector(
      `input[name="${formsetListId}-TOTAL_FORMS"]`
    );
    const mutationObserver = new MutationObserver((mutationList) => {
      mutationList.forEach((mutation) => {
        if (mutation.type !== 'childList') {
          return;
        }
        if (!(totalFormInput instanceof HTMLInputElement)) {
          console.error(
            new Error(
              'The formset list element has no TOTAL_FORMS input (did you forget to render the management form?'
            )
          );
          return;
        }
        totalFormInput.value = formsetListElement
          .getElementsByClassName('formset')
          .length.toString();
        // If nodes were not added, we're done. Otherwise, wire up the handlers.
        if (!mutation.addedNodes || !mutation.addedNodes.length) {
          return;
        }
        mutation.addedNodes.forEach((node) => {
          if (
            node instanceof HTMLElement &&
            node.classList.contains('formset')
          ) {
            attachFormsetControlHandlers(node);
          }
        });
      });
    });
    mutationObserver.observe(formsetListElement, { childList: true });
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

    Array.from(document.querySelectorAll('[data-formset-list-id]')).forEach(
      (formsetListElement) => {
        if (!(formsetListElement instanceof HTMLElement)) {
          return;
        }
        initializeFormsetListManagementForm(formsetListElement);
        Array.from(
          formsetListElement.getElementsByClassName('formset')
        ).forEach((formsetElement) => {
          if (formsetElement instanceof HTMLElement) {
            attachFormsetControlHandlers(formsetElement);
          }
        });
      }
    );

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
