import { TodoApp } from "@/components/todo-app"

export default function Home() {
  return (
    <div className="flex min-h-screen flex-1 items-center justify-center bg-zinc-50 p-8 font-sans dark:bg-black">
      <TodoApp />
    </div>
  )
}
