(() => {
  // This needs to match the animation duration in site.css
  const MESSAGE_TIMEOUT_MS = 10 * 1000;
  // These keys need to match the values of DocumentationItemFormat
  const FORMAT_OPTION_VALUE_EXTENSIONS = {
    markdown: ['md', 'markdown'],
    plaintext: ['txt'],
  };

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
  const initializeFormsetElement = (formsetElement) => {
    Array.from(
      formsetElement.querySelectorAll('[data-formset-close-trigger]')
    ).forEach((element) => {
      element.addEventListener('click', () => {
        formsetElement.remove();
      });
    });
    Array.from(
      formsetElement.querySelectorAll('[data-formset-expand-collapse-toggle]')
    ).forEach((element) => {
      element.addEventListener('click', () => {
        if (formsetElement.classList.contains('formset--collapsed')) {
          formsetElement.classList.remove('formset--collapsed');
          return;
        }
        formsetElement.classList.add('formset--collapsed');
      });
    });
    Array.from(
      formsetElement.querySelectorAll('[data-url-format-selector-for]')
    )
      .filter((element) => element instanceof HTMLSelectElement)
      .forEach((formatSelectElement) => {
        initializeFormatSelectElement(formatSelectElement);
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
  const initializeFormsetList = (formsetListElement) => {
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
        const formsetElements =
          formsetListElement.getElementsByClassName('formset');
        totalFormInput.value = formsetElements.length.toString();
        // If the number of formset items changed,
        // update any index-based values
        if (
          (mutation.addedNodes && mutation.addedNodes.length) ||
          (mutation.removedNodes && mutation.removedNodes.length)
        ) {
          Array.from(formsetElements).forEach((formsetElement, index) => {
            const count = (index + 1).toString();
            formsetElement
              .querySelectorAll('[data-formset-count]')
              .forEach((countElement) => {
                if (countElement instanceof HTMLElement) {
                  countElement.innerText = count;
                }
              });
            // Rename any attributes with the current formset index
            formsetElement.innerHTML = formsetElement.innerHTML.replace(
              new RegExp(`${formsetListId}-[\\d+]`, 'g'),
              `${formsetListId}-${index}`
            );
            if (formsetElement instanceof HTMLElement) {
              initializeFormsetElement(formsetElement);
            }
          });
        }
      });
    });
    mutationObserver.observe(formsetListElement, { childList: true });
  };

  /**
   * Pass a `select` element containing a list of file formats
   * for a paired URL field. When the URL field is changed,
   * the `select` will be updated to a matching format if possible.
   *
   * @param {HTMLSelectElement} formatSelectElement
   */
  const initializeFormatSelectElement = (formatSelectElement) => {
    const triggerElementId = formatSelectElement.getAttribute(
      'data-url-format-selector-for'
    );
    if (!triggerElementId) {
      return;
    }
    const triggerElement = document.getElementById(triggerElementId);
    // If the URL input already has a value (like when editing an existing entity), bail.
    if (!(triggerElement instanceof HTMLInputElement) || triggerElement.value) {
      return;
    }
    // Get the available formats and filter by the ones we know extensions for
    /** @type {(keyof FORMAT_OPTION_VALUE_EXTENSIONS)[]} */
    const availableFormats = Array.from(formatSelectElement.options)
      .map(({ value }) => value)
      .filter(
        /** @type {(value: string) => value is keyof FORMAT_OPTION_VALUE_EXTENSIONS } */
        (value) => value in FORMAT_OPTION_VALUE_EXTENSIONS
      );
    // When the input element changes, we'll try to match its extension.
    // If there's a match, we'll select it in the format dropdown.
    const handleTriggerElementInput = () => {
      try {
        const url = new URL(triggerElement.value);
        const matchingFormat = availableFormats.find((value) =>
          FORMAT_OPTION_VALUE_EXTENSIONS[value].find((extension) =>
            url.pathname.toLowerCase().endsWith('.' + extension)
          )
        );
        if (matchingFormat) {
          formatSelectElement.value = matchingFormat;
        }
        // eslint-disable-next-line no-unused-vars
      } catch (err) {
        // Fine; don't mess with the select element
      }
    };
    triggerElement.addEventListener('input', handleTriggerElementInput);
    // If the user manually changes the format selection,
    // stop trying to set it for them.
    // 'change' events do *not* fire when we set the value programmatically
    const handleFormatSelectElementChange = () => {
      triggerElement.removeEventListener('input', handleTriggerElementInput);
      formatSelectElement.removeEventListener(
        'change',
        handleFormatSelectElementChange
      );
    };
    formatSelectElement.addEventListener(
      'change',
      handleFormatSelectElementChange
    );
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

    Array.from(document.querySelectorAll('.js-autosubmit-select'))
      // If the input isn't in a form, there's nothing to submit
      .filter(
        /** @returns {input is (HTMLSelectElement & {form: HTMLFormElement})} */
        (input) => input instanceof HTMLSelectElement && Boolean(input.form)
      )
      .forEach((selectElement) => {
        const handleChange = () => {
          selectElement.form.submit();
        };
        selectElement.addEventListener('input', handleChange);
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
        initializeFormsetList(formsetListElement);
        Array.from(
          formsetListElement.getElementsByClassName('formset')
        ).forEach((formsetElement) => {
          if (formsetElement instanceof HTMLElement) {
            initializeFormsetElement(formsetElement);
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

    Array.from(document.querySelectorAll('[data-url-format-selector-for]'))
      .filter(
        (formatSelectElement) =>
          formatSelectElement instanceof HTMLSelectElement
      )
      .forEach((formatSelectElement) =>
        initializeFormatSelectElement(formatSelectElement)
      );

    setTimeout(() => {
      Array.from(document.querySelectorAll('.messages .message')).forEach(
        (element) => {
          element.remove();
        }
      );
    }, MESSAGE_TIMEOUT_MS);

    if (window.lucide) {
      window.lucide.createIcons();
    }
  });
})();
