import { OrganizationList, UserButton } from "@clerk/nextjs"

import { AuthShell } from "@/components/auth-shell"
import { JoinByCode } from "@/features/orgs/join-by-code"

export default function SelectOrgPage() {
  return (
    <AuthShell>
      <div className="absolute top-4 right-4">
        <UserButton />
      </div>
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Chọn tổ chức để tiếp tục</h1>
        <p className="text-sm text-muted-foreground">
          Cuộc họp và biên bản được chia sẻ trong phạm vi một tổ chức. Tạo tổ chức mới, hoặc xin vào
          tổ chức có sẵn bằng mã tham gia.
        </p>
      </div>
      <OrganizationList
        hidePersonal
        afterSelectOrganizationUrl="/"
        afterCreateOrganizationUrl="/"
      />
      <JoinByCode />
    </AuthShell>
  )
}
