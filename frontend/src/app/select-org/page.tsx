import { OrganizationList } from "@clerk/nextjs"

import { AuthShell } from "@/components/auth-shell"

export default function SelectOrgPage() {
  return (
    <AuthShell>
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Chọn tổ chức để tiếp tục</h1>
        <p className="text-sm text-muted-foreground">
          Cuộc họp và biên bản được chia sẻ trong phạm vi một tổ chức.
        </p>
      </div>
      <OrganizationList
        hidePersonal
        afterSelectOrganizationUrl="/"
        afterCreateOrganizationUrl="/"
      />
    </AuthShell>
  )
}
