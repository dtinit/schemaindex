(() => {
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
    }
  }

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
        if (input.hasAttribute('autofocus')){
          input.selectionStart = input.value.length;
        }
    });

    Array.from(document.querySelectorAll('.message-dismissal-trigger')).forEach((element) => {
      element.addEventListener('click', () => {
        if (element.parentElement){
          element.parentElement.remove(); 
        }
      })
    })
  });
 })()
