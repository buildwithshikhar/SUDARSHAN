import { expect, test } from '@playwright/test'
import { brand } from './brand'

test('loads the build-status screen with live version info', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(brand.productName)
  await expect(page.getByRole('heading', { name: 'Build status' })).toBeVisible()
  await expect(page.getByText('Reachable')).toBeVisible()
  await expect(page.getByText('Fictional scenarios · open-source parameters')).toBeVisible()
})

test('switches to Hindi and back', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'हिन्दी' }).click()
  await expect(page.getByRole('heading', { name: 'बिल्ड स्थिति' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'hi')
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('heading', { name: 'Build status' })).toBeVisible()
})

test('switches theme', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Light' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.getByRole('button', { name: 'Dark' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('is operable by keyboard alone', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Reachable')).toBeVisible()
  await page.keyboard.press('Tab') // skip link
  await page.keyboard.press('Tab') // EN
  await page.keyboard.press('Tab') // हिं
  await expect(page.getByRole('button', { name: 'हिन्दी' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'बिल्ड स्थिति' })).toBeVisible()
  await page.keyboard.press('Tab') // Dark
  await page.keyboard.press('Tab') // Light
  await page.keyboard.press('Space')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
})
