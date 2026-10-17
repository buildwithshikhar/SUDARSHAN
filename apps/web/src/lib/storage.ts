/** localStorage can throw (private windows, blocked site data); every use is guarded. */
export function readSetting(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeSetting(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* the setting simply does not persist */
  }
}
