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
})()
