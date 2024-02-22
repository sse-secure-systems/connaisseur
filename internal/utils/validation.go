package utils

import (
	"fmt"
	"reflect"

	"github.com/go-playground/locales/en"
	ut "github.com/go-playground/universal-translator"
	validation "github.com/go-playground/validator/v10"
	en_translations "github.com/go-playground/validator/v10/translations/en"
	"github.com/sirupsen/logrus"
)

func Validate(s interface{}) error {
	validate := validation.New(validation.WithRequiredStructEnabled())
	en := en.New()
	uni := ut.New(en, en)
	trans, _ := uni.GetTranslator(en.Locale())
	_ = en_translations.RegisterDefaultTranslations(validate, trans)

	_ = validate.RegisterTranslation("required_without", trans, func(ut ut.Translator) error {
		return ut.Add("required_without", "{0} must be set if {1} isn't", true) // see universal-translator for details
	}, func(ut ut.Translator, fe validation.FieldError) string {
		t, _ := ut.T("required_without", fe.Field(), fe.Param())
		return t
	})

	_ = validate.RegisterTranslation("excluded_with", trans, func(ut ut.Translator) error {
		return ut.Add("excluded_with", "{0} must not be set if {1} is", true) // see universal-translator for details
	}, func(ut ut.Translator, fe validation.FieldError) string {
		t, _ := ut.T("excluded_with", fe.Field(), fe.Param())
		return t
	})

	err := validate.Struct(s)

	if err == nil {
		return err
	}

	if ive, ok := err.(*validation.InvalidValidationError); ok {
		msg := fmt.Sprintf("validation definitions are invalid: %s", ive.Error())
		logrus.Error(msg)
		panic(msg)
	}

	ty := reflect.TypeOf(s).Name()

	msg := ""
	for i, err := range err.(validation.ValidationErrors) {
		msg += fmt.Sprintf("%s error %d: %s\n", ty, i, err.Translate(trans))
	}

	return fmt.Errorf("%s has %d errors:\n%s", ty, len(err.(validation.ValidationErrors)), msg)
}
