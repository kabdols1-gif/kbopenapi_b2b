# KB OpenAPI B2B Sample

KB 전용 OpenAPI B2B 샘플을 로컬에서 테스트하기 위한 Next.js + FastAPI 환경입니다.

## Run

- 개발 모드 실행: `start-openapi-dev.cmd` 또는 `start-openapi-test.cmd`
- 운영 모드 실행: `start-openapi-prod.cmd` 또는 `start-openapi-test.cmd /prod`
- 종료: `stop-openapi-test.cmd`
- 화면: `http://localhost:3020/openapi-test`
- 백엔드: `http://localhost:8020`

## Modes

- 개발 모드(`AIS_OPENAPI_MODE=development`)
  - FastAPI reload와 `/docs`를 켭니다.
  - CORS는 로컬 테스트 편의를 위해 전체 허용합니다.
  - `key.txt`, `~/KB/config/kb_devlp.yaml`, 로컬 KB B2B Postman 샘플 기반 기본값을 화면에 미리 채웁니다.
  - KB B2B 개발망을 기본 대상으로 사용합니다.
- 운영 모드(`AIS_OPENAPI_MODE=production`)
  - FastAPI reload와 문서 엔드포인트를 끕니다.
  - CORS는 `AIS_OPENAPI_CORS_ORIGINS`에 지정된 origin만 허용합니다.
  - 로컬 비밀값은 기본적으로 API 응답에 노출하지 않습니다.
  - KB B2B 운영망을 기본 대상으로 사용합니다.

## Environment

- 기본 포트는 백엔드 `8020`, 프론트엔드 `3020`입니다.
- 필요하면 아래 환경변수로 변경할 수 있습니다.
- `AIS_OPENAPI_MODE` (`development` 또는 `production`)
- `AIS_OPENAPI_BACKEND_PORT`
- `AIS_OPENAPI_FRONTEND_PORT`
- `AIS_OPENAPI_CORS_ORIGINS` (운영 모드에서 쉼표로 구분)
- `AIS_OPENAPI_ALLOWED_HOST_SUFFIXES` (프록시 허용 도메인 suffix, 쉼표로 구분)
- `AIS_OPENAPI_EXPOSE_LOCAL_DEFAULTS=1` (운영 모드에서 로컬 기본값 노출이 꼭 필요할 때만 사용)
- 개발/운영별 KB B2B 기본 URL은 각각 아래로 설정할 수 있습니다.
  - `AIS_OPENAPI_DEV_KB_B2B_BASE_URL`
  - `AIS_OPENAPI_PROD_KB_B2B_BASE_URL`

## Core Files

- `frontend/src/app/openapi-test`: KB B2B 테스트 화면과 샘플 카탈로그
- `frontend/src/components/openapi`: KB OpenAPI 테스트 클라이언트 UI
- `backend/settings.py`: 개발/운영 모드 환경 설정
- `backend/routers/openapi_test.py`: 외부 OpenAPI 호출 프록시
- `backend/routers/config.py`: OpenAPI 테스트 기본 설정 조회
- `backend/services/openapi_test_defaults.py`: 로컬 key/Postman/config 기반 KB B2B 기본값 생성
- `kb_auth.py`: KB B2B userInfo 암호화와 `~/KB/config/kb_devlp.yaml` 설정 로딩

## Local Secrets

`key.txt`는 로컬 테스트용 설정 파일입니다. 외부 공유 또는 커밋 대상에서 제외해야 합니다.

KB B2B 키는 아래 이름을 사용할 수 있습니다.

```txt
clientId : ...
clientSecret : ...
ciNo : ...
userInfo : ...
```

또는 `~/KB/config/kb_devlp.yaml`에 dev/prod별 `client_id`, `client_secret`, `ci_no`, `user_info`, `account`, `product_code` 값을 설정할 수 있습니다.
