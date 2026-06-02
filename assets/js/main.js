// Small progressive-enhancement helpers. The site is fully readable without JS.
;(function () {
    'use strict'

    // Current year in the footer.
    var yearEl = document.getElementById('year')
    if (yearEl) {
        yearEl.textContent = String(new Date().getFullYear())
    }

    // Light/dark theme toggle, persisted in localStorage.
    var root = document.documentElement
    var toggle = document.getElementById('theme-toggle')
    var stored = null
    try {
        stored = localStorage.getItem('theme')
    } catch (e) {
        stored = null
    }
    if (stored === 'light' || stored === 'dark') {
        root.setAttribute('data-theme', stored)
    }
    if (toggle) {
        toggle.addEventListener('click', function () {
            var prefersDark = window.matchMedia(
                '(prefers-color-scheme: dark)'
            ).matches
            var current =
                root.getAttribute('data-theme') ||
                (prefersDark ? 'dark' : 'light')
            var next = current === 'dark' ? 'light' : 'dark'
            root.setAttribute('data-theme', next)
            try {
                localStorage.setItem('theme', next)
            } catch (e) {
                /* ignore */
            }
        })
    }

    // Mobile navigation menu toggle.
    var nav = document.querySelector('.nav')
    var navToggle = document.getElementById('nav-toggle')
    function closeNav() {
        if (nav && nav.classList.contains('nav-open')) {
            nav.classList.remove('nav-open')
            if (navToggle) {
                navToggle.setAttribute('aria-expanded', 'false')
            }
        }
    }
    if (nav && navToggle) {
        navToggle.addEventListener('click', function () {
            var open = nav.classList.toggle('nav-open')
            navToggle.setAttribute('aria-expanded', open ? 'true' : 'false')
        })
        // Close when tapping outside the header or pressing Escape.
        document.addEventListener('click', function (event) {
            if (!nav.contains(event.target)) {
                closeNav()
            }
        })
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeNav()
            }
        })
    }
})()
