import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const language of ['English', 'हिन्दी']) {
  for (const theme of ['Dark', 'Light']) {
    test(`has no axe violations: ${language}, ${theme}`, async ({ page }) => {
      await page.goto('/')
      await page.getByRole('button', { name: language }).click()
      await page
        .getByRole('button', { name: language === 'English' ? theme : themeHi(theme) })
        .click()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme.toLowerCase())
      await expect(page.getByText(/Reachable|उपलब्ध/)).toBeVisible()
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()
      expect(results.violations).toEqual([])
    })
  }
}

function themeHi(theme: string): string {
  return theme === 'Dark' ? 'गहरा' : 'हल्का'
}
