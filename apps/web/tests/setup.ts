import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import { setCsrfToken } from '../src/lib/api'
import { setLanguage, setTheme } from '../src/lib/prefs'

// jsdom does not implement the modal <dialog> methods.
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}

afterEach(() => {
  cleanup()
  setCsrfToken(null)
  setTheme('dark')
  setLanguage('en')
  window.localStorage.clear()
})
