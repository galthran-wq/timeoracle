import { createI18n } from 'vue-i18n'
import en from './en'
import ru from './ru'
import guideEn from './guide-en'
import guideRu from './guide-ru'

export type SupportedLocale = 'en' | 'ru'

export const LOCALE_OPTIONS: { label: string; value: SupportedLocale }[] = [
  { label: 'EN', value: 'en' },
  { label: 'RU', value: 'ru' },
]

function detectLocale(): SupportedLocale {
  const stored = localStorage.getItem('locale')
  if (stored === 'en' || stored === 'ru') return stored
  const browserLang = navigator.language.slice(0, 2)
  if (browserLang === 'ru') return 'ru'
  return 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: {
    en: { ...en, guide: guideEn },
    ru: { ...ru, guide: guideRu },
  },
})

export default i18n
