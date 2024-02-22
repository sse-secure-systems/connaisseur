package alerting

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/utils"
	"fmt"
	"os"
	"regexp"
	"strings"

	"github.com/iancoleman/strcase"
)

func transformTemplate(template string) (string, error) {
	path, err := utils.SafeFileName(
		constants.AlertTemplateDir,
		fmt.Sprintf("%s.json", template),
	)
	if err != nil {
		return "", fmt.Errorf(
			"unable to get template file: %s",
			err,
		)
	}

	bytes, err := os.ReadFile(path) // #nosec G304 False positive since we use SafeFileName
	if err != nil {
		return "", fmt.Errorf("failed to read template file: %s", err)
	}

	re := regexp.MustCompile(`{{[^{}]*}}`)
	bytes = re.ReplaceAllFunc(bytes, transformJinjaToGo)

	return string(bytes), nil
}

func transformJinjaToGo(match []byte) []byte {
	str := strings.TrimSpace(string(match))

	camelCase := strcase.ToCamel(str)

	return []byte(fmt.Sprintf("{{ .%s }}", camelCase))
}

func templateWithPayloadFields(template map[string]interface{}, payloadFields map[string]interface{}) map[string]interface{} {
	for key, value := range payloadFields {
		template[key] = value
	}
	return template
}
