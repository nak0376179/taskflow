"use client"

import { useEffect, useState } from "react"
import { Trash2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"

type Todo = {
  id: string
  text: string
  done: boolean
}

type Filter = "all" | "active" | "done"

const STORAGE_KEY = "taskflow.todos"

export function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [text, setText] = useState("")
  const [filter, setFilter] = useState<Filter>("all")
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw) {
      try {
        // one-time sync from localStorage on mount; must run after hydration, not during render
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTodos(JSON.parse(raw))
      } catch {
        // ignore malformed storage
      }
    }
    setLoaded(true)
  }, [])

  useEffect(() => {
    if (!loaded) return
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(todos))
  }, [todos, loaded])

  function addTodo() {
    const value = text.trim()
    if (!value) return
    setTodos((prev) => [
      { id: crypto.randomUUID(), text: value, done: false },
      ...prev,
    ])
    setText("")
  }

  function toggleTodo(id: string) {
    setTodos((prev) =>
      prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t))
    )
  }

  function deleteTodo(id: string) {
    setTodos((prev) => prev.filter((t) => t.id !== id))
  }

  function clearDone() {
    setTodos((prev) => prev.filter((t) => !t.done))
  }

  const filteredTodos = todos.filter((t) => {
    if (filter === "active") return !t.done
    if (filter === "done") return t.done
    return true
  })

  const remaining = todos.filter((t) => !t.done).length

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl">TaskFlow</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            addTodo()
          }}
        >
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="やることを入力..."
            aria-label="新しいタスク"
          />
          <Button type="submit">追加</Button>
        </form>

        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {(["all", "active", "done"] as const).map((f) => (
              <Button
                key={f}
                type="button"
                size="sm"
                variant={filter === f ? "secondary" : "ghost"}
                onClick={() => setFilter(f)}
              >
                {f === "all" ? "すべて" : f === "active" ? "未完了" : "完了"}
              </Button>
            ))}
          </div>
          <Badge variant="secondary">{remaining} 件残り</Badge>
        </div>

        <Separator />

        <ul className="flex flex-col gap-2">
          {filteredTodos.length === 0 && (
            <li className="py-6 text-center text-sm text-muted-foreground">
              タスクはありません
            </li>
          )}
          {filteredTodos.map((todo) => (
            <li
              key={todo.id}
              className="group flex items-center gap-3 rounded-md border border-transparent px-2 py-1.5 hover:border-border hover:bg-muted/50"
            >
              <Checkbox
                id={todo.id}
                checked={todo.done}
                onCheckedChange={() => toggleTodo(todo.id)}
              />
              <Label
                htmlFor={todo.id}
                className={
                  "flex-1 cursor-pointer text-sm font-normal " +
                  (todo.done ? "text-muted-foreground line-through" : "")
                }
              >
                {todo.text}
              </Label>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="opacity-0 group-hover:opacity-100"
                aria-label="削除"
                onClick={() => deleteTodo(todo.id)}
              >
                <Trash2Icon className="text-destructive" />
              </Button>
            </li>
          ))}
        </ul>

        {todos.some((t) => t.done) && (
          <>
            <Separator />
            <Button variant="ghost" size="sm" onClick={clearDone}>
              完了したタスクを削除
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}
