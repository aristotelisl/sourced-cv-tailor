// Drag-to-reorder with native HTML5 drag and drop: drag an item by its handle, drop it on another
// item of the same list. Lists are told apart by `group`, so nested lists (bullets inside entries
// inside sections) don't catch each other's drops.
import { type DragEvent, useState } from 'react'

let dragging: { group: string; index: number } | null = null

export function useDragReorder(group: string, onMove: (from: number, to: number) => void) {
  const [over, setOver] = useState<number | null>(null)
  const mine = () => dragging?.group === group

  return {
    /** The index currently dragged over, for a drop indicator. */
    over,
    /** Props for the drag handle. The item it sits in (see `target`) is what's shown while dragging. */
    handle: (index: number) => ({
      draggable: true,
      onDragStart: (e: DragEvent) => {
        e.stopPropagation()
        dragging = { group, index }
        e.dataTransfer.effectAllowed = 'move'
        e.dataTransfer.setData('text/plain', group)
        const item = (e.currentTarget as HTMLElement).closest('[data-drag-item]')
        if (item) e.dataTransfer.setDragImage(item, 12, 12)
      },
      onDragEnd: () => {
        dragging = null
        setOver(null)
      },
    }),
    /** Props for each item that accepts drops. */
    target: (index: number) => ({
      'data-drag-item': '',
      onDragOver: (e: DragEvent) => {
        if (!mine()) return
        e.preventDefault()
        e.stopPropagation()
        setOver(index)
      },
      onDragLeave: () => setOver(o => (o === index ? null : o)),
      onDrop: (e: DragEvent) => {
        if (!mine()) return
        e.preventDefault()
        e.stopPropagation()
        if (dragging!.index !== index) onMove(dragging!.index, index)
        dragging = null
        setOver(null)
      },
    }),
  }
}
