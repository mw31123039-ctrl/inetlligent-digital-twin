import type { SymptomService } from '../types'
import { characterOptions, getRegion, onsetOptions } from '../data/regions'

/** Replace this adapter with fetch calls to Laravel later. No UI component calls a network API. */
export function createMockSymptomService(options: { delay?: number; shouldFail?: () => boolean } = {}): SymptomService {
  return {
    async respond(region, step, answer) {
      if (!answer.trim()) throw new Error('Please describe your symptoms or choose an answer.')
      if (answer.length > 500) throw new Error('Please keep your answer under 500 characters.')
      await new Promise(resolve => setTimeout(resolve, options.delay ?? 650))
      if (options.shouldFail?.()) throw new Error('The demo response could not be loaded. Your answer is safe. Please try again.')
      const scripts = [
        { message: getRegion(region).locationQuestion, options: getRegion(region).locations, complete: false },
        { message: 'When did you first notice this?', options: onsetOptions, complete: false },
        { message: 'How would you describe the pattern?', options: characterOptions, complete: false },
        { message: 'Thank you. Your demonstration summary is ready. You can adjust the pain level, add a note, or save this assessment. These scripted responses do not provide a diagnosis.', options: [], complete: true },
      ]
      if (step >= 4) return { message: 'Your note has been added to the demonstration summary. You can save or export the updated assessment.', options: [], complete: true }
      return scripts[Math.min(Math.max(step, 0), scripts.length - 1)]!
    },
  }
}
