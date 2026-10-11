import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

describe("UI kit smoke", () => {
  it("renders a button", () => {
    render(<Button>Lưu</Button>)
    expect(screen.getByRole("button", { name: "Lưu" })).toBeInTheDocument()
  })

  it("renders a destructive badge", () => {
    render(<Badge variant="destructive">Lỗi</Badge>)
    expect(screen.getByText("Lỗi")).toBeInTheDocument()
  })
})
