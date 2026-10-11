import { OrganizationList } from "@clerk/nextjs"

export default function SelectOrgPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-4">
      <h1 className="text-xl font-semibold">Chọn tổ chức để tiếp tục</h1>
      <OrganizationList
        hidePersonal
        afterSelectOrganizationUrl="/"
        afterCreateOrganizationUrl="/"
      />
    </main>
  )
}
