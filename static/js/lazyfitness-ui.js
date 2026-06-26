(function () {
  'use strict';

  const activePanels = new Set();

  function getTargetElement(trigger) {
    const selector = trigger.dataset.lfTarget || trigger.getAttribute('href');
    if (!selector || selector === '#') {
      return null;
    }
    try {
      return document.querySelector(selector);
    } catch (error) {
      return null;
    }
  }

  function showElement(element) {
    element.classList.add('show');
    element.removeAttribute('hidden');
  }

  function hideElement(element) {
    element.classList.remove('show');
    if (element.classList.contains('modal') || element.classList.contains('offcanvas')) {
      element.setAttribute('hidden', 'hidden');
    }
  }

  function closeOverlays(type) {
    document.querySelectorAll(type).forEach((element) => {
      hideElement(element);
    });
    document.body.classList.remove('lf-overlay-open');
  }

  function openOverlay(element) {
    showElement(element);
    document.body.classList.add('lf-overlay-open');
    activePanels.add(element);
  }

  function toggleCollapse(element, trigger) {
    const isOpen = element.classList.toggle('show');
    if (trigger) {
      trigger.setAttribute('aria-expanded', String(isOpen));
    }
  }

  function toggleDropdown(trigger) {
    const menu = trigger.parentElement.querySelector('.dropdown-menu');
    if (!menu) {
      return;
    }

    const isOpen = menu.classList.contains('show');
    document.querySelectorAll('.dropdown-menu.show').forEach((item) => item.classList.remove('show'));
    menu.classList.toggle('show', !isOpen);
    trigger.setAttribute('aria-expanded', String(!isOpen));
  }

  document.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-lf-toggle]');
    if (toggle) {
      const action = toggle.dataset.lfToggle;
      const target = getTargetElement(toggle);

      if (action === 'dropdown') {
        event.preventDefault();
        toggleDropdown(toggle);
        return;
      }

      if (!target) {
        return;
      }

      if (action === 'collapse') {
        event.preventDefault();
        toggleCollapse(target, toggle);
      }

      if (action === 'modal') {
        event.preventDefault();
        closeOverlays('.modal.show');
        openOverlay(target);
      }

      if (action === 'offcanvas') {
        event.preventDefault();
        closeOverlays('.offcanvas.show');
        openOverlay(target);
      }
    }

    const dismiss = event.target.closest('[data-lf-dismiss]');
    if (dismiss) {
      const action = dismiss.dataset.lfDismiss;
      const target = dismiss.closest(`.${action}`);
      if (target) {
        hideElement(target);
      }
      if (action === 'modal' || action === 'offcanvas') {
        document.body.classList.remove('lf-overlay-open');
      }
    }

    if (!event.target.closest('.dropdown')) {
      document.querySelectorAll('.dropdown-menu.show').forEach((item) => item.classList.remove('show'));
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeOverlays('.modal.show');
      closeOverlays('.offcanvas.show');
      document.querySelectorAll('.dropdown-menu.show').forEach((item) => item.classList.remove('show'));
    }
  });

  document.querySelectorAll('.toast').forEach((toast) => {
    showElement(toast);
    const delay = Number.parseInt(toast.dataset.lfDelay || '2800', 10);
    const autoHide = toast.dataset.lfAutohide !== 'false';

    if (autoHide) {
      window.setTimeout(() => hideElement(toast), delay);
    }
  });

  document.querySelectorAll('.modal, .offcanvas').forEach((element) => {
    if (!element.classList.contains('show')) {
      element.setAttribute('hidden', 'hidden');
    }
  });

  document.querySelectorAll('[data-lf-back]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.preventDefault(); // Prevents default button behavior
      
      const fallback = button.dataset.fallback || '/';
      const nextUrl = new URLSearchParams(window.location.search).get('next');
      
      if (nextUrl && nextUrl.startsWith('/') && !nextUrl.startsWith('//')) {
        window.location.href = nextUrl;
        return;
      }

      if (window.history.length > 1 && document.referrer.includes(window.location.origin)) {
        window.history.back();
        return;
      }

      window.location.href = fallback;
    });
  });
})();
